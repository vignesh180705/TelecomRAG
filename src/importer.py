import json
import hashlib
from collections import defaultdict

from neo4j import GraphDatabase

from config import (
    NEO4J_URI,
    NEO4J_USERNAME,
    NEO4J_PASSWORD,
    JSON_FILE,
    BATCH_SIZE,
)


# ============================================================
# ENTITY TYPE -> NEO4J LABEL
# ============================================================

ENTITY_LABELS = {
    "NETWORK_FUNCTION": "NetworkFunction",
    "NETWORK_ENTITY": "NetworkEntity",
    "INTERFACE": "Interface",
    "PROTOCOL": "Protocol",
    "PROCEDURE": "Procedure",
    "STATE": "State",
    "PARAMETER": "Parameter",
    "INFORMATION_ELEMENT": "InformationElement",
    "QOS_CONCEPT": "QoSConcept",
    "SECURITY_CONCEPT": "SecurityConcept",
    "NETWORK_SLICE": "NetworkSlice",
    "SERVICE": "Service",
    "USE_CASE": "UseCase",
    "REQUIREMENT": "Requirement",
    "PERFORMANCE_METRIC": "PerformanceMetric",
    "RESOURCE": "Resource",
    "APPLICATION": "Application",
    "ANALYTICS_CONCEPT": "AnalyticsConcept",
}


# ============================================================
# UTILITY
# ============================================================

def chunks(items, size):

    for i in range(0, len(items), size):
        yield items[i:i + size]


def make_mention_id(entity_id, document, page, evidence):

    raw = (
        f"{entity_id}|"
        f"{document}|"
        f"{page}|"
        f"{evidence}"
    )

    return hashlib.sha256(
        raw.encode("utf-8")
    ).hexdigest()


# ============================================================
# IMPORTER
# ============================================================

class ThreeGPPImporter:

    def __init__(self):

        self.driver = GraphDatabase.driver(
            NEO4J_URI,
            auth=(
                NEO4J_USERNAME,
                NEO4J_PASSWORD
            )
        )

    def close(self):

        self.driver.close()

    # --------------------------------------------------------
    # LOAD JSON
    # --------------------------------------------------------

    def load_json(self):

        print(f"Loading JSON: {JSON_FILE}")

        with open(
            JSON_FILE,
            "r",
            encoding="utf-8"
        ) as f:

            data = json.load(f)

        print("JSON loaded.")

        return data

    # --------------------------------------------------------
    # IMPORT ENTITIES
    # --------------------------------------------------------

    def import_entities(self, entities):

        groups = defaultdict(list)

        for entity in entities:

            entity_type = entity.get(
                "entity_type"
            )

            groups[entity_type].append(entity)

        print(
            f"Found {len(entities):,} entities "
            f"across {len(groups)} entity types."
        )

        for entity_type, group in groups.items():

            label = ENTITY_LABELS.get(
                entity_type
            )

            if not label:

                print(
                    f"WARNING: Unknown entity type: "
                    f"{entity_type}"
                )

                continue

            print(
                f"\nImporting {entity_type}: "
                f"{len(group):,} entities"
            )

            for batch in chunks(
                group,
                BATCH_SIZE
            ):

                self._import_entity_batch(
                    batch,
                    label
                )

    # --------------------------------------------------------
    # ENTITY BATCH
    # --------------------------------------------------------

    def _import_entity_batch(
        self,
        entities,
        label
    ):

        query = f"""
        UNWIND $rows AS row

        MERGE (e:Entity:{label} {{
            entity_id: row.entity_id
        }})

        SET
            e.canonical_name =
                row.canonical_name,

            e.entity_type =
                row.entity_type,

            e.aliases =
                row.aliases,

            e.description =
                row.description,

            e.source_count =
                row.source_count,

            e.mention_count =
                row.mention_count,

            e.resolved_from_count =
                row.resolved_from_count
        """

        rows = []

        for entity in entities:

            properties = entity.get(
                "properties",
                {}
            )

            rows.append({

                "entity_id":
                    entity.get("entity_id"),

                "canonical_name":
                    entity.get(
                        "canonical_name"
                    ),

                "entity_type":
                    entity.get(
                        "entity_type"
                    ),

                "aliases":
                    entity.get(
                        "aliases",
                        []
                    ),

                "description":
                    entity.get(
                        "description"
                    ),

                "source_count":
                    properties.get(
                        "source_count",
                        0
                    ),

                "mention_count":
                    properties.get(
                        "mention_count",
                        0
                    ),

                "resolved_from_count":
                    properties.get(
                        "resolved_from_count",
                        0
                    ),
            })

        with self.driver.session() as session:

            session.run(
                query,
                rows=rows
            )

    # --------------------------------------------------------
    # IMPORT DOCUMENTS
    # --------------------------------------------------------

    def import_documents(
        self,
        source_documents
    ):

        if not source_documents:

            print(
                "No source_documents found."
            )

            return

        print(
            f"\nImporting "
            f"{len(source_documents):,} documents"
        )

        rows = []

        for document in source_documents:

            if isinstance(
                document,
                str
            ):

                rows.append({
                    "document_id":
                        document,

                    "filename":
                        document
                })

            elif isinstance(
                document,
                dict
            ):

                document_id = (
                    document.get(
                        "document_id"
                    )
                    or document.get(
                        "filename"
                    )
                    or document.get(
                        "document"
                    )
                )

                rows.append({
                    "document_id":
                        document_id,

                    "filename":
                        document.get(
                            "filename",
                            document_id
                        )
                })

        for batch in chunks(
            rows,
            BATCH_SIZE
        ):

            self._import_document_batch(
                batch
            )

    # --------------------------------------------------------
    # DOCUMENT BATCH
    # --------------------------------------------------------

    def _import_document_batch(
        self,
        rows
    ):

        query = """

        UNWIND $rows AS row

        MERGE (d:Document {
            document_id: row.document_id
        })

        SET d.filename =
            row.filename

        """

        with self.driver.session() as session:

            session.run(
                query,
                rows=rows
            )

    # --------------------------------------------------------
    # SOURCE MENTIONS
    # --------------------------------------------------------

    def import_source_mentions(
        self,
        entities
    ):

        print("\nPreparing source mentions...")

        rows = []

        for entity in entities:

            entity_id = entity.get(
                "entity_id"
            )

            mentions = entity.get(
                "source_mentions",
                []
            )

            for mention in mentions:

                document = mention.get(
                    "document"
                )

                page = mention.get(
                    "page"
                )

                evidence = mention.get(
                    "evidence"
                )

                if not document:

                    continue

                mention_id = make_mention_id(
                    entity_id,
                    document,
                    page,
                    evidence
                )

                rows.append({

                    "mention_id":
                        mention_id,

                    "entity_id":
                        entity_id,

                    "document":
                        document,

                    "page":
                        page,

                    "evidence":
                        evidence
                })

        print(
            f"Found {len(rows):,} source mentions."
        )

        for batch in chunks(
            rows,
            BATCH_SIZE
        ):

            self._import_mentions_batch(
                batch
            )

    # --------------------------------------------------------
    # MENTION BATCH
    # --------------------------------------------------------

    def _import_mentions_batch(
        self,
        rows
    ):

        query = """

        UNWIND $rows AS row

        MATCH (e:Entity {
            entity_id: row.entity_id
        })

        MERGE (d:Document {
            document_id: row.document
        })

        MERGE (m:SourceMention {
            mention_id: row.mention_id
        })

        SET
            m.page =
                row.page,

            m.evidence =
                row.evidence

        MERGE (e)-[:HAS_MENTION]->(m)

        MERGE (m)-[:IN_DOCUMENT]->(d)

        """

        with self.driver.session() as session:

            session.run(
                query,
                rows=rows
            )

    # --------------------------------------------------------
    # RUN
    # --------------------------------------------------------

    def run(self):

        data = self.load_json()

        entities = data.get(
            "entities",
            []
        )

        source_documents = data.get(
            "source_documents",
            []
        )

        print("\n==============================")
        print("3GPP NEO4J IMPORT")
        print("==============================")

        print(
            f"Entities: {len(entities):,}"
        )

        print(
            f"Documents: "
            f"{len(source_documents):,}"
        )

        # 1. Entities
        self.import_entities(
            entities
        )

        # 2. Documents
        self.import_documents(
            source_documents
        )

        # 3. PDF provenance
        self.import_source_mentions(
            entities
        )

        print("\n==============================")
        print("IMPORT COMPLETE")
        print("==============================")

