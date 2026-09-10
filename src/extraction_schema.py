from pydantic import BaseModel, Field


class Entity(BaseModel):
    name: str = Field(min_length=1)
    entity_type: str = Field(min_length=1)
    description: str = ""
    evidence: str = ""


class Relationship(BaseModel):
    source: str = Field(min_length=1)
    relationship: str = Field(min_length=1)
    target: str = Field(min_length=1)
    evidence: str = ""


class ChunkExtraction(BaseModel):
    chunk_id: str = Field(min_length=1)
    entities: list[Entity] = []
    relationships: list[Relationship] = []
