from bs4 import BeautifulSoup
import csv
from PyQt6.QtWidgets import QFileDialog


class LapDataParser:
    def __init__(self):
        pass

    def extract_name(self, cell):
        return cell.split(':', 1)[-1].strip() if ':' in cell else cell.strip()


    def process_and_save_csv(self, raw_data:str):
        soup = BeautifulSoup(raw_data, "html.parser")
        rows = []

        for tr in soup.find_all("tr"):
            row = []
            for td in tr.find_all("td"):
                # Extract all <p> inside <td> as separate lines, join with newline or space
                texts = [p.get_text(strip=True) for p in td.find_all("p")]
                cell_text = "\n".join(texts) if texts else td.get_text(strip=True)
                row.append(cell_text)
            rows.append(row)

        header_row = rows[0]
        cleaned_header = [header_row[0]] + [self.extract_name(cell) for cell in header_row[1:]]
        rows[0] = cleaned_header

        filename, _ = QFileDialog.getSaveFileName(None, "Save CSV", "outputFiles", "CSV Files (*.csv);;All Files (*)")
        if filename:
            with open(filename, "w", newline="", encoding="utf-8") as f:
                writer = csv.writer(f)
                writer.writerows(rows)
            print(f"Saved at Location: {filename}")

