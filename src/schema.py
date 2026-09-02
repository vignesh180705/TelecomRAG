from typing import Literal

EntityType = Literal[
    "NETWORK_FUNCTION",
    "NETWORK_ENTITY",
    "USER_EQUIPMENT",
    "RADIO_NODE",
    "INTERFACE",
    "PROTOCOL",
    "PROCEDURE",
    "SESSION",
    "QOS_CONCEPT",
    "NETWORK_SLICE",
    "CAPABILITY",
    "PARAMETER",
    "INFORMATION_ELEMENT",
    "MESSAGE",
    "REQUIREMENT",
]


# ============================================================
# RELATIONSHIP TYPES
# ============================================================

RelationType = Literal[
    "COMMUNICATES_WITH",
    "USES_INTERFACE",
    "USES_PROTOCOL",
    "INVOLVES",
    "ESTABLISHES",
    "CONTAINS",
    "SUPPORTS",
    "CONNECTS_TO",
    "HAS_CAPABILITY",
    "HAS_PARAMETER",
    "CONTAINS_INFORMATION_ELEMENT",
    "USES_MESSAGE",
    "APPLIES_TO",
    "DEPENDS_ON",
]


# ============================================================
# VALIDATION SCHEMA
# ============================================================

validation_schema = {

    "NETWORK_FUNCTION": [
        "COMMUNICATES_WITH",
        "USES_INTERFACE",
        "USES_PROTOCOL",
        "INVOLVES",
        "SUPPORTS",
        "HAS_CAPABILITY",
        "HAS_PARAMETER",
        "USES_MESSAGE",
        "DEPENDS_ON",
    ],

    "NETWORK_ENTITY": [
        "COMMUNICATES_WITH",
        "USES_INTERFACE",
        "USES_PROTOCOL",
        "INVOLVES",
        "SUPPORTS",
        "HAS_CAPABILITY",
        "HAS_PARAMETER",
        "CONNECTS_TO",
        "DEPENDS_ON",
    ],

    "USER_EQUIPMENT": [
        "CONNECTS_TO",
        "ESTABLISHES",
        "SUPPORTS",
        "HAS_CAPABILITY",
        "HAS_PARAMETER",
        "USES_PROTOCOL",
        "INVOLVES",
    ],

    "RADIO_NODE": [
        "COMMUNICATES_WITH",
        "USES_INTERFACE",
        "USES_PROTOCOL",
        "CONNECTS_TO",
        "SUPPORTS",
        "HAS_CAPABILITY",
        "HAS_PARAMETER",
    ],

    "INTERFACE": [
        "USES_PROTOCOL",
        "CONNECTS_TO",
    ],

    "PROTOCOL": [
        "USES_MESSAGE",
        "CONTAINS_INFORMATION_ELEMENT",
    ],

    "PROCEDURE": [
        "INVOLVES",
        "USES_MESSAGE",
        "USES_PROTOCOL",
        "ESTABLISHES",
        "APPLIES_TO",
        "DEPENDS_ON",
    ],

    "SESSION": [
        "CONTAINS",
        "USES_PROTOCOL",
        "INVOLVES",
        "APPLIES_TO",
    ],

    "QOS_CONCEPT": [
        "CONTAINS",
        "HAS_PARAMETER",
        "DEPENDS_ON",
        "APPLIES_TO",
    ],

    "NETWORK_SLICE": [
        "SUPPORTS",
        "HAS_PARAMETER",
        "APPLIES_TO",
        "DEPENDS_ON",
    ],

    "CAPABILITY": [
        "HAS_PARAMETER",
        "APPLIES_TO",
        "DEPENDS_ON",
    ],

    "PARAMETER": [
        "DEPENDS_ON",
    ],

    "INFORMATION_ELEMENT": [
        "DEPENDS_ON",
    ],

    "MESSAGE": [
        "CONTAINS_INFORMATION_ELEMENT",
        "USES_PROTOCOL",
    ],

    "REQUIREMENT": [
        "APPLIES_TO",
        "DEPENDS_ON",
    ],
}

ENTITY_DESCRIPTIONS = {

    "NETWORK_FUNCTION":
        "A standardized 3GPP network function providing one or more "
        "network services, such as AMF, SMF, UPF, PCF, UDM, or AUSF.",

    "NETWORK_ENTITY":
        "A major network-level entity or system component, such as "
        "5GC, NG-RAN, RAN, or a core network component.",

    "USER_EQUIPMENT":
        "A user device or terminal participating in a 3GPP network.",

    "RADIO_NODE":
        "A radio access network node such as gNB or ng-eNB.",

    "INTERFACE":
        "A standardized interface or reference point connecting "
        "network entities or functions, such as N1, N2, N3, or N4.",

    "PROTOCOL":
        "A communication protocol used by 3GPP network entities.",

    "PROCEDURE":
        "A standardized signaling or operational procedure defined "
        "by 3GPP specifications.",

    "SESSION":
        "A network session established for communication or service, "
        "such as a PDU Session.",

    "QOS_CONCEPT":
        "A concept related to quality of service, such as a QoS Flow "
        "or 5QI.",

    "NETWORK_SLICE":
        "A logical network slice or slicing-related concept defined "
        "by 3GPP.",

    "CAPABILITY":
        "A capability supported by a network function, network entity, "
        "radio node, or user equipment.",

    "PARAMETER":
        "A technical parameter, configuration value, or standardized "
        "attribute relevant to a 3GPP entity or procedure.",

    "INFORMATION_ELEMENT":
        "A structured information element carried by a protocol message.",

    "MESSAGE":
        "A signaling or protocol message exchanged between network entities.",

    "REQUIREMENT":
        "A normative or technical requirement specified by a 3GPP document.",
}