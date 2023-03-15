import logging
from typing import List, Optional, Tuple, Union

import torch
import torch.nn
from torch.nn.utils.rnn import pad_sequence
from tqdm import tqdm

import flair.nn
from flair.data import Dictionary, Sentence, Span, get_spans_from_bio
from flair.datasets import DataLoader, FlairDatapointDataset
from flair.embeddings import DocumentEmbeddings, TokenEmbeddings
from flair.embeddings.base import load_embeddings
from flair.training_utils import store_embeddings

log = logging.getLogger("flair")


class DualEncoder(flair.nn.Classifier[Sentence]):
    def __init__(
        self,
        token_encoder: TokenEmbeddings,
        label_encoder: DocumentEmbeddings,
        tag_dictionary: Dictionary,
        tag_type: str,
        tag_format: str = "BIO",
        dropout: float = 0.0,
    ):
        super(DualEncoder, self).__init__()

        # ----- Create the internal tag dictionary -----
        self.tag_type = tag_type
        self.tag_format = tag_format.upper()
        self._init_verbalizers_and_tag_dictionary(tag_dictionary)

        # ----- Embeddings -----
        self.token_encoder = token_encoder
        self.label_encoder = label_encoder
        self.use_dropout: float = dropout

        if dropout > 0.0:
            self.dropout = torch.nn.Dropout(dropout)

        self.loss_fct = torch.nn.CrossEntropyLoss(reduction="sum")

    def _init_verbalizers_and_tag_dictionary(self, tag_dictionary):
        if tag_dictionary.span_labels:
            # the big question is whether the label dictionary should contain an UNK or not
            # without UNK, we cannot evaluate on data that contains labels not seen in test
            # with UNK, the model learns less well if there are no UNK examples
            self.label_dictionary = Dictionary(add_unk=False)
            assert self.tag_format in ["BIOES", "BIO"]
            for label in tag_dictionary.get_items():
                if label == "<unk>":
                    continue
                self.label_dictionary.add_item("O")
                if self.tag_format == "BIOES":
                    self.label_dictionary.add_item("S-" + label)
                    self.label_dictionary.add_item("B-" + label)
                    self.label_dictionary.add_item("E-" + label)
                    self.label_dictionary.add_item("I-" + label)
                if self.tag_format == "BIO":
                    self.label_dictionary.add_item("B-" + label)
                    self.label_dictionary.add_item("I-" + label)
        else:
            self.label_dictionary = tag_dictionary

        # is this a span prediction problem?
        self.predict_spans = tag_dictionary.span_labels

        self.idx2verbalized_label = {}
        for label, idx in self.label_dictionary.item2idx.items():
            label = label.decode("utf-8")
            if label == "O":
                self.idx2verbalized_label[idx] = "other"
            elif label.startswith("B-"):
                self.idx2verbalized_label[idx] = "begin " + label.split("-")[1]
            elif label.startswith("I-"):
                self.idx2verbalized_label[idx] = "inside " + label.split("-")[1]

        self.tagset_size = len(self.label_dictionary)
        log.info(f"DualEncoder predicts: {self.label_dictionary}")

    @property
    def label_type(self):
        return self.tag_type

    def forward(self, sentences, inference, return_features):
        # embed sentences
        self.token_encoder.embed(sentences)

        # get all tokens in this batch
        all_tokens_in_batch = [token for sentence in sentences for token in sentence]

        # get a tensor of all token embeddings
        token_embedding_tensor = torch.stack([token.get_embedding() for token in all_tokens_in_batch])

        # embed the verbalized labels to make a label tensor
        verbalized_labels = list(map(Sentence, self.idx2verbalized_label.values()))
        self.label_encoder.embed(verbalized_labels)
        label_tensor = [label.get_embedding() for label in verbalized_labels]

        # do the dot product to calculate the logits
        logits = torch.mm(token_embedding_tensor, torch.stack(label_tensor).T)

        # for loss computation, get the gold labels
        gold_label_tensor = torch.tensor(
            [
                self.label_dictionary.get_idx_for_item(label)
                for sentence in self._get_gold_labels(sentences)
                for label in sentence
            ],
            device=flair.device,
        )

        # compute loss
        loss = self.loss_fct(logits, gold_label_tensor)

        # if doing inference, return loss and predictions
        if inference and return_features:
            # do softmax + argmax
            scores, preds = torch.max(torch.nn.functional.softmax(logits, dim=-1), dim=-1)

            # create a pad mask
            mask = [torch.tensor([True for _ in sentence]).to(flair.device) for sentence in sentences]
            pad_mask = pad_sequence(mask, batch_first=True, padding_value=-False)

            # Format into batch size x sequence length without padding
            scores = [
                _scores.detach().cpu().tolist()
                for _scores in torch.split(scores, pad_mask.sum(dim=-1).detach().tolist())
            ]
            preds = [
                _preds.detach().cpu().tolist() for _preds in torch.split(preds, pad_mask.sum(dim=-1).detach().tolist())
            ]

            decoded_predictions = [
                [
                    (self.label_dictionary.get_item_for_index(pred), score)
                    for pred, score in zip(sentence_preds, sentence_scores)
                ]
                for sentence_preds, sentence_scores in zip(preds, scores)
            ]

            return loss, decoded_predictions, logits

        # otherwise just return the loss
        elif return_features:
            return loss, logits
        else:
            return loss

    def forward_loss(self, sentences: List[Sentence]) -> Tuple[torch.Tensor, int]:
        if len(sentences) == 0:
            return torch.tensor(0.0, dtype=torch.float, device=flair.device, requires_grad=True), 0

        loss = self.forward(sentences, inference=False, return_features=False)

        return loss, sum([len(s) for s in sentences])

    def predict(
        self,
        sentences: Union[List[Sentence], Sentence],
        mini_batch_size: int = 32,
        return_probabilities_for_all_classes: bool = False,
        verbose: bool = False,
        label_name: Optional[str] = None,
        return_loss=False,
        embedding_storage_mode="none",
        force_token_predictions: bool = False,
    ):  # type: ignore
        """
        Predicts labels for current batch with CRF or Softmax.
        :param sentences: List of sentences in batch
        :param mini_batch_size: batch size for test data
        :param return_probabilities_for_all_classes: Whether to return probabilities for all classes
        :param verbose: whether to use progress bar
        :param label_name: which label to predict
        :param return_loss: whether to return loss value
        :param embedding_storage_mode: determines where to store embeddings - can be "gpu", "cpu" or None.
        """
        if label_name is None:
            label_name = self.tag_type

        with torch.no_grad():
            if not sentences:
                return sentences

            if len(sentences) == 0:
                return sentences

            # make sure it's a list
            if not isinstance(sentences, list) and not isinstance(sentences, flair.data.Dataset):
                sentences = [sentences]

            # filter empty sentences
            sentences = [sentence for sentence in sentences if len(sentence) > 0]

            dataloader = DataLoader(
                dataset=FlairDatapointDataset(sentences),
                batch_size=mini_batch_size,
            )
            # progress bar for verbosity
            if verbose:
                dataloader = tqdm(dataloader, desc="Batch inference")

            overall_loss = torch.zeros(1, device=flair.device)
            label_count = 0
            for batch in dataloader:
                # stop if all sentences are empty
                if not batch:
                    continue

                for sentence in batch:
                    sentence.remove_labels(label_name)

                loss, preds = self.forward(batch, inference=True, return_features=False)

                # if return_loss, get loss value
                if return_loss:
                    overall_loss += loss.item()
                    label_count += sum([len(p) for p in preds])

                # add predictions to Sentence
                for sentence, sentence_predictions in zip(batch, preds):
                    # BIOES-labels need to be converted to spans
                    if self.predict_spans and not force_token_predictions:
                        sentence_tags = [label[0] for label in sentence_predictions]
                        sentence_scores = [label[1] for label in sentence_predictions]
                        predicted_spans = get_spans_from_bio(sentence_tags, sentence_scores)
                        for predicted_span in predicted_spans:
                            span: Span = sentence[predicted_span[0][0] : predicted_span[0][-1] + 1]
                            span.add_label(label_name, value=predicted_span[2], score=predicted_span[1])

                    # token-labels can be added directly ("O" and legacy "_" predictions are skipped)
                    else:
                        for token, label in zip(sentence.tokens, sentence_predictions):
                            if label[0] in ["O", "_"]:
                                continue
                            token.add_label(typename=label_name, value=label[0], score=label[1])

                store_embeddings(sentences, storage_mode=embedding_storage_mode)

            if return_loss:
                return overall_loss, label_count

    def _get_gold_labels(self, sentences: List[Sentence]) -> List[List[str]]:
        """
        Extracts gold labels from each sentence.
        :param sentences: List of sentences in batch
        """
        # spans need to be encoded as token-level predictions
        if self.predict_spans:
            all_sentence_labels = []
            for sentence in sentences:
                sentence_labels = ["O"] * len(sentence)
                for label in sentence.get_labels(self.label_type):
                    span: Span = label.data_point
                    if self.tag_format == "BIOES":
                        if len(span) == 1:
                            sentence_labels[span[0].idx - 1] = "S-" + label.value
                        else:
                            sentence_labels[span[0].idx - 1] = "B-" + label.value
                            sentence_labels[span[-1].idx - 1] = "E-" + label.value
                            for i in range(span[0].idx, span[-1].idx - 1):
                                sentence_labels[i] = "I-" + label.value
                    else:
                        sentence_labels[span[0].idx - 1] = "B-" + label.value
                        for i in range(span[0].idx, span[-1].idx):
                            sentence_labels[i] = "I-" + label.value
                all_sentence_labels.append(sentence_labels)
            labels = all_sentence_labels

        # all others are regular labels for each token
        else:
            labels = [[token.get_label(self.label_type, "O").value for token in sentence] for sentence in sentences]

        return labels

    def _print_predictions(self, batch, gold_label_type):
        lines = []
        if self.predict_spans:
            for datapoint in batch:
                # all labels default to "O"
                for token in datapoint:
                    token.set_label("gold_bio", "O")
                    token.set_label("predicted_bio", "O")

                # set gold token-level
                for gold_label in datapoint.get_labels(gold_label_type):
                    gold_span: Span = gold_label.data_point
                    prefix = "B-"
                    for token in gold_span:
                        token.set_label("gold_bio", prefix + gold_label.value)
                        prefix = "I-"

                # set predicted token-level
                for predicted_label in datapoint.get_labels("predicted"):
                    predicted_span: Span = predicted_label.data_point
                    prefix = "B-"
                    for token in predicted_span:
                        token.set_label("predicted_bio", prefix + predicted_label.value)
                        prefix = "I-"

                # now print labels in CoNLL format
                for token in datapoint:
                    eval_line = (
                        f"{token.text} "
                        f"{token.get_label('gold_bio').value} "
                        f"{token.get_label('predicted_bio').value}\n"
                    )
                    lines.append(eval_line)
                lines.append("\n")

        else:
            for datapoint in batch:
                # print labels in CoNLL format
                for token in datapoint:
                    eval_line = (
                        f"{token.text} "
                        f"{token.get_label(gold_label_type).value} "
                        f"{token.get_label('predicted').value}\n"
                    )
                    lines.append(eval_line)
                lines.append("\n")
        return lines

    def _get_state_dict(self):
        """Returns the state dictionary for this model."""
        model_state = {
            **super()._get_state_dict(),
            "token_encoder": self.token_encoder.save_embeddings(use_state_dict=False),
            "label_encoder": self.label_encoder.save_embeddings(use_state_dict=False),
            "tag_dictionary": self.label_dictionary,
            "tag_format": self.tag_format,
            "tag_type": self.tag_type,
            "use_dropout": self.use_dropout,
        }

        return model_state

    @classmethod
    def _init_model_with_state_dict(cls, state, **kwargs):
        token_encoder = state.pop("token_encoder")
        if isinstance(token_encoder, dict):
            token_encoder = load_embeddings(token_encoder)
        state["token_encoder"] = token_encoder

        label_encoder = state.pop("label_encoder")
        if isinstance(label_encoder, dict):
            label_encoder = load_embeddings(label_encoder)
        state["label_encoder"] = label_encoder

        return super()._init_model_with_state_dict(
            state,
            token_encoder=state.get("token_encoder"),
            label_encoder=state.get("label_encoder"),
            tag_dictionary=state.get("tag_dictionary"),
            tag_format=state.get("tag_format", "BIO"),
            tag_type=state.get("tag_type"),
            dropout=state.get("use_dropout", 0.0),
        )
