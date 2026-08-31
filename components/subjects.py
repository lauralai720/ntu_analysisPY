from dataclasses import dataclass,field
from typing import Optional

from components.esi_year import ESIYear


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
    YearList : list[int] = field(default_factory=list)
    Subject1Type : str = ""
    Subject2Type : str = ""
    ShownByESI_ID: bool = False # ESIFieldSelectedValue.ShownByESI_ID



## Copy一個新的Subjects物件
## 因為有dll裡的物件，所以不能用python的copy.deepcopy來進行複製
def copy_subjects(subjs: Subjects) -> Subjects:
    new_subjs = Subjects(
        subject1=subjs.subject1,
        subject2=subjs.subject2,
        year=subjs.year,
        subj1BindCol=subjs.subj1BindCol,
        subj2BindCol =subjs.subj2BindCol,
        yearBindCol =subjs.yearBindCol,
        selectedVal1 =subjs.selectedVal1,
        selectedVal2 =subjs.selectedVal2,
        selectedYear =subjs.selectedYear,
        Subject1Header =subjs.Subject1Header,
        Subject2Header =subjs.Subject2Header,
        YearHeader =subjs.YearHeader,
        YearList =subjs.YearList,
        Subject1Type =subjs.Subject1Type,
        Subject2Type =subjs.Subject2Type,
        ShownByESI_ID =subjs.ShownByESI_ID,
    )
    return new_subjs
