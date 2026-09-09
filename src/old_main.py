from schema_loader import Neo4jSchema
from importer import ThreeGPPImporter


def old_main():

    print("================================")
    print("3GPP Knowledge Graph Builder")
    print("================================")

    # --------------------------------
    # 1. Neo4j schema
    # --------------------------------

    print("\nCreating Neo4j schema...")

    schema = Neo4jSchema()

    try:

        schema.create_constraints()
        schema.create_indexes()

    finally:

        schema.close()

    # --------------------------------
    # 2. Import graph
    # --------------------------------

    importer = ThreeGPPImporter()

    try:

        importer.run()

    finally:

        importer.close()


if __name__ == "__main__":
    old_main()