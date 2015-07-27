

class ReportTransform(object):

    # *_id maps a source section id to a target section id
    # *_map maps fields inside the section from source to target id
    # if the names are equal, a simple string can be specified instead
    # of a two-tuple

    time_id = None

    blue_id = (None, None)
    blue_map = []

    radio_id = (None, None)
    cell_id = (None, None)
    cell_map = []

    position_id = (None, None)
    position_map = []

    toplevel_id = (None, None)
    toplevel_map = []

    wifi_id = (None, None)
    wifi_map = []

    def conditional_set(self, item, target, value):
        if value is not None:
            item[target] = value

    def _map_dict(self, item_source, field_map):
        value = {}
        for spec in field_map:
            if isinstance(spec, tuple):
                source, target = spec
            else:
                source = spec
                target = spec
            self.conditional_set(value, target,
                                 item_source.get(source))
        return value

    def _parse_dict(self, item, report, key_map, field_map):
        value = {}
        if key_map[0] is None:
            item_source = item
        else:
            item_source = item.get(key_map[0])
        if item_source:
            value = self._map_dict(item_source, field_map)
        if value:
            if key_map[1] is None:
                report.update(value)
            else:  # pragma: no cover
                report[key_map[1]] = value
        return value

    def _parse_list(self, item, report, key_map, field_map):
        values = []
        for value_item in item.get(key_map[0], ()):
            value = self._map_dict(value_item, field_map)
            if value:
                values.append(value)
        if values:
            report[key_map[1]] = values
        return values

    def _parse_cells(self, item, report, key_map, field_map):
        cells = []
        for cell_item in item.get(key_map[0], ()):
            cell = self._map_dict(cell_item, field_map)
            if cell:
                cells.append(cell)
        if cells:
            report[key_map[1]] = cells
        return cells

    def transform_one(self, item):
        report = {}
        self._parse_dict(item, report, self.position_id, self.position_map)
        self._parse_dict(item, report, self.toplevel_id, self.toplevel_map)

        timestamp = item.get(self.time_id)
        if timestamp:
            report['timestamp'] = timestamp

        blues = self._parse_list(item, report, self.blue_id, self.blue_map)
        cells = self._parse_cells(item, report, self.cell_id, self.cell_map)
        wifis = self._parse_list(item, report, self.wifi_id, self.wifi_map)

        if blues or cells or wifis:
            return report
        return {}
