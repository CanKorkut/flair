import argparse
from pathlib import Path

import flair
from flair.models import SequenceTagger
from flair.optim import LinearSchedulerWithWarmup
from flair.trainers import ModelTrainer
from flair.training_utils import AnnealOnPlateau
from local_corpora import get_corpus


def main(args):
    if args.cuda:
        flair.device = f"cuda:{args.cuda_device}"

    save_base_path = Path(
        f"{args.cache_path}/pretrained-flert/"
        f"{args.transformer}{'-context' if args.use_context else ''}_{args.corpus}{args.fewnerd_granularity}_{args.lr}_{args.seed}_LPFT-model/"
    )

    corpus = get_corpus(args.corpus, args.fewnerd_granularity)

    # 4. initialize fine-tuneable transformer embeddings WITH document context
    tagger = SequenceTagger.load(args.pretrained_model_path)

    # 6. initialize trainer
    trainer = ModelTrainer(tagger, corpus)

    # 7. run fine-tuning
    trainer.fine_tune(
        save_base_path,
        learning_rate=args.lr,
        mini_batch_size=args.bs,
        mini_batch_chunk_size=args.mbs,
        max_epochs=args.epochs,
        scheduler=AnnealOnPlateau if args.early_stopping else LinearSchedulerWithWarmup,
        train_with_dev=args.early_stopping,
        min_learning_rate=args.min_lr if args.early_stopping else 0.001,
        save_final_model=True,
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--cuda", type=bool, default=True)
    parser.add_argument("--cuda_device", type=int, default=2)
    parser.add_argument("--seed", type=int, default=123)
    parser.add_argument("--cache_path", type=str, default="/glusterfs/dfs-gfs-dist/goldejon/flair-models")
    parser.add_argument("--pretrained_model_path", type=str)
    parser.add_argument("--corpus", type=str, default="ontonotes")
    parser.add_argument("--fewnerd_granularity", type=str, default="")
    parser.add_argument("--transformer", type=str, default="bert-base-uncased")
    parser.add_argument("--use_context", action="store_true")
    parser.add_argument("--lr", type=float, default=1e-5)
    parser.add_argument("--bs", type=int, default=4)
    parser.add_argument("--mbs", type=int, default=4)
    parser.add_argument("--epochs", type=int, default=10)
    parser.add_argument("--early_stopping", type=bool, default=False)
    parser.add_argument("--min_lr", type=float, default=5e-7)
    args = parser.parse_args()
    main(args)
