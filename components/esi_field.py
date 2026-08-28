from dataclasses import dataclass
from collections import defaultdict

@dataclass
class ESIField:
    fid : int = 0
    group_name :str =""
    field_name :str =""

class ESIFieldGroup:
    def __init__(self, field_group_name: str, field_list: list[ESIField]):
        self.field_group_name = field_group_name
        self.fields = field_list

class ESIFieldValueInfo:
    def __init__(self, query_list: list[list[str]]):
        self.field_groups : list[ESIFieldGroup] = []
        temp_dict = defaultdict(list)
        for q in query_list:
            group_name = q[0]
            field_name = q[1]
            fid = int(q[2])
            esi_field = ESIField(fid = fid, group_name= group_name, field_name= field_name)
            temp_dict[group_name].append(esi_field)

        for key, value in temp_dict.items():
            self.field_groups.append(ESIFieldGroup(field_group_name=key, field_list=value))

        self.str_to_field : dict[str, dict[str,ESIField]] = {}
        self.fid_to_field : dict[int, ESIField] = {}

        for fg in self.field_groups:
            if fg.field_group_name not in self.str_to_field:
                self.str_to_field[fg.field_group_name] = {}
            for f in fg.fields:
                self.fid_to_field[f.fid] = f
                self.str_to_field[fg.field_group_name][f.field_name] = f
