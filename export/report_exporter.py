## PRISAnalyzer.PresidentReportESI.Class.Analysis.Templates.ReportExporter

from dataclasses import dataclass, field
from openpyxl import Workbook

# PRIS
from components.template import Template
from export.excel_report import *

## 輸出成excel
## 統整所有sheet
@dataclass
class ReportExporter:
    #兩個list的位置是有對應的
    templates : list[Template] = field(default_factory=list)
    templates_rows : list[list[list[str]]] = field(default_factory=list)

    def add_item(self, template: Template, template_row: list[list[str]]):
        self.templates.append(template)
        self.templates_rows.append(template_row)

    # 匯出Excel檔案 - 對外入口
    def export(self, path : str):
        wb = Workbook()
        # openpyxl 預設會自動建立一個 "Sheet" 工作表,先移除
        if "Sheet" in wb.sheetnames:
            del wb["Sheet"]

        # 目錄Sheet
        self.create_table_of_contents(wb, self.templates)

        # 各類型的分析報表
        for r in range(len(self.templates)):
            self.templates[r].to_worksheet(wb=wb, rows= self.templates_rows[r])

        # 隱藏計算無排版的報表
        self.hide_all_rawdata_tabs(wb)

        wb.save(path)
            

    def create_table_of_contents(self, wb: Workbook, templates: list[Template]):
        excel_report = ExcelReport()

        header1 = ExcelColumnHeader(name= "表單名", width=15)
        header2 = ExcelColumnHeader(name= "表單內容", width=150)

        headers = [header1, header2]
        excel_report.headers = headers
        
        rows : list[list[ECell]] = []
        for temp in templates:
            row = [
                ECell(text=temp.sheet_tab_name),
                ECell(
                    text=temp.sheet_name, 
                    horizontal_align="left", 
                    hyperlink=f"#'{temp.sheet_tab_name}'!A1",
                )
            ]
            rows.append(row)

        excel_report.rows = rows
        excel_report.export(wb, "目錄")

    def hide_all_rawdata_tabs(self,  wb: Workbook):
        for sheet in wb.worksheets:
            if sheet.title.endswith(Template.RawdataSheetSuffix):
                sheet.sheet_state = "hidden"
