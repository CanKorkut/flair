from torch.utils.data.dataset import Subset

from flair.datasets import CONLL_03, FEWNERD, ONTONOTES, WNUT_17


def get_corpus(corpus: str, fewnerd_granularity: str):
    if corpus == "wnut_17":
        return WNUT_17(
            label_name_map={
                "corporation": "corporation",
                "creative-work": "creative work",
                "group": "group",
                "location": "location",
                "person": "person",
                "product": "product",
            }
        )
    elif corpus == "conll_03":
        dataset = CONLL_03(
            base_path="data",
            column_format={0: "text", 1: "pos", 2: "chunk", 3: "ner"},
            label_name_map={"PER": "person", "LOC": "location", "ORG": "organization", "MISC": "miscellaneous"},
        )
        valid_indices = []
        for idx, sentence in enumerate(dataset.train):
            if "DOCSTART" not in sentence.text:
                valid_indices.append(idx)
        dataset._train = Subset(dataset._train, valid_indices)
        return dataset
    elif corpus == "ontonotes":
        return ONTONOTES(
            label_name_map={
                "CARDINAL": "cardinal",
                "DATE": "date",
                "EVENT": "event",
                "FAC": "facility",
                "GPE": "geographical social political entity",
                "LANGUAGE": "language",
                "LAW": "law",
                "LOC": "location",
                "MONEY": "money",
                "NORP": "nationality religion political",
                "ORDINAL": "ordinal",
                "ORG": "organization",
                "PERCENT": "percent",
                "PERSON": "person",
                "PRODUCT": "product",
                "QUANTITY": "quantity",
                "TIME": "time",
                "WORK_OF_ART": "work of art",
            }
        )
    elif corpus == "fewnerd":
        if fewnerd_granularity == "fine":
            return FEWNERD(
                label_name_map={
                    "location-GPE": "geographical social political entity",
                    "person-other": "other person",
                    "organization-other": "other organization",
                    "organization-company": "company",
                    "person-artist/author": "author artist",
                    "person-athlete": "athlete",
                    "person-politician": "politician",
                    "building-other": "other building",
                    "organization-sportsteam": "sportsteam",
                    "organization-education": "eduction",
                    "location-other": "other location",
                    "other-biologything": "biology",
                    "location-road/railway/highway/transit": "road railway highway transit",
                    "person-actor": "actor",
                    "product-other": "other product",
                    "event-sportsevent": "sportsevent",
                    "organization-government/governmentagency": "government agency",
                    "location-bodiesofwater": "bodies of water",
                    "organization-media/newspaper": "media newspaper",
                    "art-music": "music",
                    "other-chemicalthing": "chemical",
                    "event-attack/battle/war/militaryconflict": "attack war battle military conflict",
                    "organization-politicalparty": "political party",
                    "art-writtenart": "written art",
                    "other-award": "award",
                    "other-livingthing": "living thing",
                    "event-other": "other event",
                    "art-film": "film",
                    "product-software": "software",
                    "organization-sportsleague": "sportsleague",
                    "other-language": "language",
                    "other-disease": "disease",
                    "organization-showorganization": "show organization",
                    "product-airplane": "airplane",
                    "other-astronomything": "astronomy",
                    "organization-religion": "religion",
                    "product-car": "car",
                    "person-scholar": "scholar",
                    "other-currency": "currency",
                    "person-soldier": "soldier",
                    "location-mountain": "mountain",
                    "art-broadcastprogram": "broadcastprogram",
                    "location-island": "island",
                    "art-other": "other art",
                    "person-director": "director",
                    "product-weapon": "weapon",
                    "other-god": "god",
                    "building-theater": "theater",
                    "other-law": "law",
                    "product-food": "food",
                    "other-medical": "medical",
                    "product-game": "game",
                    "location-park": "park",
                    "product-ship": "ship",
                    "building-sportsfacility": "sportsfacility",
                    "other-educationaldegree": "educational degree",
                    "building-airport": "airport",
                    "building-hospital": "hospital",
                    "product-train": "train",
                    "building-library": "library",
                    "building-hotel": "hotel",
                    "building-restaurant": "restaurant",
                    "event-disaster": "disaster",
                    "event-election": "election",
                    "event-protest": "protest",
                    "art-painting": "painting",
                }
            )
        elif fewnerd_granularity == "coarse":
            return FEWNERD(
                label_name_map={
                    "location-GPE": "location",
                    "person-other": "person",
                    "organization-other": "organization",
                    "organization-company": "organization",
                    "person-artist/author": "person",
                    "person-athlete": "person",
                    "person-politician": "person",
                    "building-other": "building",
                    "organization-sportsteam": "organization",
                    "organization-education": "organization",
                    "location-other": "location",
                    "other-biologything": "biology",
                    "location-road/railway/highway/transit": "location",
                    "person-actor": "person",
                    "product-other": "product",
                    "event-sportsevent": "event",
                    "organization-government/governmentagency": "organization",
                    "location-bodiesofwater": "location",
                    "organization-media/newspaper": "organization",
                    "art-music": "art",
                    "other-chemicalthing": "chemical",
                    "event-attack/battle/war/militaryconflict": "event",
                    "organization-politicalparty": "organization",
                    "art-writtenart": "art",
                    "other-award": "award",
                    "other-livingthing": "living thing",
                    "event-other": "event",
                    "art-film": "art",
                    "product-software": "product",
                    "organization-sportsleague": "organization",
                    "other-language": "language",
                    "other-disease": "disease",
                    "organization-showorganization": "organization",
                    "product-airplane": "product",
                    "other-astronomything": "astronomy",
                    "organization-religion": "organization",
                    "product-car": "product",
                    "person-scholar": "person",
                    "other-currency": "currency",
                    "person-soldier": "person",
                    "location-mountain": "location",
                    "art-broadcastprogram": "art",
                    "location-island": "location",
                    "art-other": "art",
                    "person-director": "person",
                    "product-weapon": "product",
                    "other-god": "god",
                    "building-theater": "building",
                    "other-law": "law",
                    "product-food": "product",
                    "other-medical": "medical",
                    "product-game": "product",
                    "location-park": "location",
                    "product-ship": "product",
                    "building-sportsfacility": "building",
                    "other-educationaldegree": "educational degree",
                    "building-airport": "building",
                    "building-hospital": "building",
                    "product-train": "product",
                    "building-library": "building",
                    "building-hotel": "building",
                    "building-restaurant": "building",
                    "event-disaster": "event",
                    "event-election": "event",
                    "event-protest": "event",
                    "art-painting": "art",
                }
            )
    else:
        raise Exception("no valid corpus.")
