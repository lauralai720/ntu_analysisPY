from dataclasses import dataclass,field
from typing import Optional

from components.year_selector import ESIYear
from components.paper_org_value import PaperOrgSelectedValue
from database import *

@dataclass
class Subjects:
    subject1: Optional["Subject"] = None
    subject2 : Optional["Subject"] = None
    year : Optional["Subject"] = None
    subj1BindCol : dict[str, "Column"] = field(default_factory=dict)
    subj2BindCol : dict[str, "Column"] = field(default_factory=dict)
    yearBindCol : dict[str, "Column"] = field(default_factory=dict)
    selectedVal1 : list[str] = field(default_factory=list)
    selectedVal2 : list[str] = field(default_factory=list)
    selectedYear : list[ESIYear] = field(default_factory=list)
    Subject1Header : str = ""
    Subject2Header : str = ""
    YearHeader : str = ""
    YearList : list = field(default_factory=list)
    Subject1Type : str = ""
    Subject2Type : str = ""
    ShownByESI_ID: bool = False # ESIFieldSelectedValue.ShownByESI_ID
    WOSselectedVal1 : PaperOrgSelectedValue = None
    WOSselectedVal2 = None

    @property
    def subject_num(self) -> int:
        num = 0
        if self.subject1:
            num = num +1
        if self.subject2:
            num = num +1
        if self.year:
            num = num +1
        return num

