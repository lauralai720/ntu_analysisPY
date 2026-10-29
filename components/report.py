from dataclasses import dataclass, field
from exceptions import PRISError
from components.template import TemplateType
import common.util as Util
from datetime import datetime

@dataclass
class Report:
    _analysis_type_str:str= ""
    project_name: str = "" # file_name
    shown_time: str = ""
    year_list : list[str] = field(default_factory=list)
    output_path : str = ""

    @property
    def output_file(self)->str:
        now = datetime.now().strftime("%y%m%d%H%M%S")
        filename = f"{self.analysis_file_tag}{self.project_name}_{now}"
        output = f"{self.output_path}{filename}.xlsx"

        if output:
            print(f"你選擇的資料夾:{output}")
        else:
            raise PRISError("沒有選擇資料夾")
        return output

    @property
    def analysis_file_tag(self)->str:
        '''取得輸出Excel檔名前面的分析報表類型tag字串，目前有[ESI]跟[WOS]'''
        return self._analysis_type_str
    
@dataclass
class PresidentESIReport(Report):
    _analysis_type_str:str ="[ESI]"
    items: list["PresidentESIReportItem"]= field(default_factory=list)

@dataclass
class PresidentESIReportItem:
    Name: str
    Type: TemplateType
    Index: int = 0
    numCHArr = ["一", "二", "三", "四", "五", "六", "七", "八", "九"]

    def __str__(self) -> str:
        return f"{self.Name} | {self.Type.value}"

    def to_sheet_header_name(self, esi_report : PresidentESIReport) -> str:
        result = self.Name.replace("[專案名]", esi_report.project_name)
        result = result.replace("[表N]", f"表{self.get_num_ch(self.Index)}、")
        result = result.replace("[時間]", esi_report.shown_time)
        return result
    
    def get_num_ch(self,i) -> str:
        if (i <=0 or i >= 100):
            raise PRISError(f"表單Index數值不正確，{i}，正確範圍1~99")
        return Util.get_num_ch(i)


@dataclass
class PresidentWOSReport(Report):
    _analysis_type_str:str = "[WOS]"
    items : list["PresidentWOSReportItem"] = field(default_factory=list)
    year_list : list[str] = field(default_factory=list)

@dataclass
class PresidentWOSReportItem:
    type : TemplateType
    tab_name: str    # excel 工作表名稱
    sheet_name:str   # 報表上方的名稱
    index: int = 0