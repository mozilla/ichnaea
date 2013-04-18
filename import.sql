.separator ","
.import data/cells.txt cell

CREATE INDEX cell_idx ON cell(mcc, mnc, lac, cid);
CREATE INDEX cell_idx2 ON cell(mcc, mnc, cid);
