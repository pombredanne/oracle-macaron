# Copyright (c) 2022 - 2023, Oracle and/or its affiliates. All rights reserved.
# Licensed under the Universal Permissive License v 1.0 as shown at https://oss.oracle.com/licenses/upl/.

"""This module contains the CheckResult class for storing the result of a check."""
from dataclasses import dataclass, field
from enum import Enum
from heapq import heappush
from typing import TypedDict

from sqlalchemy import String
from sqlalchemy.orm import DeclarativeBase

from macaron.slsa_analyzer.provenance.expectations.expectation import Expectation
from macaron.slsa_analyzer.slsa_req import BUILD_REQ_DESC, ReqName

ResultTables = list[DeclarativeBase | Expectation]


class CheckResultType(str, Enum):
    """This class contains the types of a check result."""

    PASSED = "PASSED"
    FAILED = "FAILED"
    # A check is skipped from another check's result.
    SKIPPED = "SKIPPED"
    # A check is disabled from the user configuration.
    DISABLED = "DISABLED"
    # The result of the check is unknown or Macaron cannot resolve the
    # implementation of this check.
    UNKNOWN = "UNKNOWN"

class JustificationType(str, Enum):
    """This class contains the type of a justification that will be used in creating the HTML report."""

    #: If a justification has a text type, it will be added as a plain text.
    TEXT = "text"

    #: If a justification has a href type, it will be added as a hyperlink.
    HREF = "href"

class Confidence(float, Enum):
    """This class contains confidence score for a check result.
    
    The scores must be in [0.0, 1.0].
    """

    #: A high confidence score.
    HIGH = 1.0

    #: A medium confidence score.
    MEDIUM = 0.7

    #: A low confidence score.
    LOW = 0.5
    

@dataclass(frozen=True)
class CheckInfo:
    """This class identifies and describes a check."""

    #: The id of the check.
    check_id: str

    #: The description of the check.
    check_description: str

    #: The list of SLSA requirements that this check addresses.
    eval_reqs: list[ReqName]


@dataclass(frozen=True)
class CheckResultData:
    """This class stores the result of a check."""

    #: List of result tables produced by the check.
    result_tables: ResultTables

    #: Result type of the check (e.g. PASSED).
    result_type: CheckResultType

    #: Check result justification when for some reason the check has not run or succeeded.
    exit_justification: list[str] | None = field(default=None)

    @property
    def justification_report(self) -> list:
        # List of justifications describing the reasons for the check result.
        # If an element in the justification is a string,
        # it will be displayed as a string, if it is a mapping,
        # the value will be rendered as a hyperlink in the html report.
        if self.exit_justification:
            return [(Confidence.HIGH, self.exit_justification)]

        if not self.result_tables:
            return [(Confidence.HIGH, ["Check has failed"])]
        just_list = []
        for result in self.result_tables:
            
            dict_justifications = {}
            list_justifications = []
            for col in result.__table__.columns:
                if col.info.get("justification") and getattr(result, col.name):
                    if col.info.get("justification") == JustificationType.HREF:
                        dict_justifications[col.name] = getattr(result, col.name)
                    elif col.info.get("justification") == JustificationType.TEXT:
                        list_justifications.append(f"{col.name}: {getattr(result, col.name)}")

            if dict_justifications:
                list_justifications.append(dict_justifications)
            heappush(just_list, (result.confidence, list_justifications))
        return just_list


@dataclass(frozen=True)
class CheckResult:
    """This class stores the result of a check, including the description of the check that produced it."""

    #: Info about the check that produced these results.
    check: CheckInfo

    #: The results produced by the check.
    result: CheckResultData

    def get_summary(self) -> dict:
        """Get a flattened dictionary representation for this CheckResult, in a format suitable for the output report.

        The SLSA requirements, in particular, are translated into a list of their textual descriptions, to be suitable
        for display to users in the output report (as opposed to the internal representation as a list of enum identifiers).

        Returns
        -------
        dict
        """
        return {
            "check_id": self.check.check_id,
            "check_description": self.check.check_description,
            "slsa_requirements": [str(BUILD_REQ_DESC.get(req)) for req in self.check.eval_reqs],
            "justification": self.result.justification_report[0][1],
            "result_tables": self.result.result_tables,
            "result_type": self.result.result_type,
        }


class SkippedInfo(TypedDict):
    """This class stores the information about a skipped check."""

    check_id: str
    suppress_comment: str


def get_result_as_bool(check_result_type: CheckResultType) -> bool:
    """Return the CheckResultType as bool.

    This method returns True only if the result type is PASSED else it returns False.

    Parameters
    ----------
    check_result_type : CheckResultType
        The check result type to return the bool value.

    Returns
    -------
    bool
    """
    if check_result_type in (CheckResultType.FAILED, CheckResultType.UNKNOWN):
        return False

    return True
