import os
import pdfplumber
import re


# Funkcja do odczytu tekstu z pliku PDF
def extract_text_from_pdf(pdf_path):
    with pdfplumber.open(pdf_path) as pdf:
        text = ""
        for page in pdf.pages:
            text += page.extract_text()
    return text


# Funkcja do wyciągania podsumowania z faktury
def extract_invoice_summary(pdf_text):
    podsumowanie_pattern = r"Wartość netto:\s*([\d,.]+)\s*Podatek:\s*([\d,.]+)\s*Do zapłaty:\s*([\d,.]+)PLN"
    data_wystawienia_pattern = r"Data wystawienia:\s*(\d{4}-\d{2}-\d{2})"

    podsumowanie_match = re.search(podsumowanie_pattern, pdf_text)
    data_wystawienia_match = re.search(data_wystawienia_pattern, pdf_text)

    if podsumowanie_match and data_wystawienia_match:
        kwota_netto = podsumowanie_match.group(1).replace(',', '.')
        podatek = podsumowanie_match.group(2).replace(',', '.')
        kwota_brutto = podsumowanie_match.group(3).replace(',', '.')
        data_wystawienia = data_wystawienia_match.group(1)

        return {
            "Kwota netto": kwota_netto,
            "Podatek": podatek,
            "Kwota brutto": kwota_brutto,
            "Data wystawienia": data_wystawienia
        }
    else:
        return {
            "Kwota netto": "Brak danych",
            "Podatek": "Brak danych",
            "Kwota brutto": "Brak danych",
            "Data wystawienia": "Brak danych"
        }


# Funkcja do wyciągania danych z faktur korygujących
def parse_correction_invoice(file_name, pdf_text):
    lines = pdf_text.split("\n")

    invoices = []
    current_invoice = None
    for i, line in enumerate(lines):
        line = line.strip().replace("\xad", "")

        if line.startswith("Dotyczy dokumentu"):
            if current_invoice:
                invoices.append(current_invoice)
            current_invoice = {"Numer korekty": file_name, "Dokument korygowany": "", "Kwota brutto": 0, "Kwota netto": 0, "Podatek": 0}
            part = line.split(" ")
            dokument_korygowany = part[1].split(":")[1]
            current_invoice["Dokument korygowany"] = dokument_korygowany
        if line.__contains__("Kod podatku Stawka VAT Podstawa Kwota podatku Wartość brutto"):
            if i + 1 < len(lines):
                splitted = lines[i + 1].split()
                brutto = splitted[4].replace("\xad", "")

                netto = splitted[2].replace("\xad", "")
                podatek = splitted[3].replace("\xad", "")

                current_invoice["Podatek"] = podatek
                current_invoice["Kwota netto"] = netto

                current_invoice["Kwota brutto"] = float(brutto.replace(',', '.')) * -1
                current_invoice["Podatek"] = float(podatek.replace(',', '.')) * -1
                current_invoice["Kwota netto"] = float(netto.replace(',', '.')) * -1
    if current_invoice:
        invoices.append(current_invoice)

    return invoices


# Funkcja do znalezienia plików PDF zaczynających się od "FV"
def find_files_with_prefix(directory, prefix="FV"):
    file_list = []
    if not os.path.isdir(directory):
        print(f"Błąd: '{directory}' nie jest katalogiem!")
        return []
    for filename in os.listdir(directory):
        if filename.startswith(prefix) and filename.endswith('.pdf'):
            file_list.append(filename)
    return file_list


# Funkcja do generowania pliku HTML na podstawie szablonu
def generate_html_from_template(directory, files, template_path, output_path, all_invoices):
    table_rows = ""

    # Przetwarzamy najpierw faktury VAT (FV)
    for fv in files:
        if '-K' not in fv:  # Ignorujemy faktury korygujące na razie
            pdf_path = os.path.join(directory, fv)
            pdf_text = extract_text_from_pdf(pdf_path)
            results = extract_invoice_summary(pdf_text)
            kwota_netto = results.get("Kwota netto", "Brak danych")
            podatek = results.get("Podatek", "Brak danych")
            kwota_brutto = results.get("Kwota brutto", "Brak danych")
            data_wystawienia = results.get("Data wystawienia", "Brak danych")

            # Dodaj fakturę do tabeli
            table_rows += f"<tr><td>{fv}</td><td>{fv}</td><td>{data_wystawienia}</td><td>---</td><td>{kwota_netto}</td><td>{podatek}</td><td>{kwota_brutto}</td><td>Standardowa</td><td>{get_rozliczeniowy_miesiac(data_wystawienia)}</td></tr>\n"

            # Dodajemy fakturę do listy faktur dla dopasowania z korektami
            all_invoices.append({
                "Numer faktury": fv,
                "Data wystawienia": data_wystawienia,
                "Kwota netto": kwota_netto,
                "Podatek": podatek,
                "Kwota brutto": kwota_brutto
            })

    # Następnie przetwarzamy faktury korygujące (FV-K)
    for fv in files:
        if '-K' in fv:
            pdf_path = os.path.join(directory, fv)
            pdf_text = extract_text_from_pdf(pdf_path)
            results_correction = parse_correction_invoice(fv, pdf_text)
            for correction in results_correction:
                kwota_brutto = correction["Kwota brutto"]
                dokument_korygowany = correction["Dokument korygowany"]
                kwota_netto = correction["Kwota netto"]
                podatek = correction["Podatek"]
                miesiac_rozliczeniowy = get_miesiac_z_faktury_korygowanej(dokument_korygowany, all_invoices)

                # Dodaj korektę do tabeli
                table_rows += f"<tr><td>{fv}</td><td>{fv}</td><td>---</td><td>{dokument_korygowany}</td><td>{kwota_netto}</td><td>{podatek}</td><td>{kwota_brutto}</td><td>Korekta</td><td>{miesiac_rozliczeniowy}</td></tr>\n"

    # Wstaw wygenerowane wiersze do szablonu
    with open(template_path, "r", encoding="utf-8") as file:
        template = file.read()

    html_content = template.replace("{{table_rows}}", table_rows)

    # Zapisz wynikowy plik HTML
    with open(output_path, "w", encoding="utf-8") as output_file:
        output_file.write(html_content)


# Funkcja do wyciągania miesiąca rozliczeniowego
def get_rozliczeniowy_miesiac(data_wystawienia):
    miesiace_polskie = {
        1: "Styczeń", 2: "Luty", 3: "Marzec", 4: "Kwiecień", 5: "Maj", 6: "Czerwiec",
        7: "Lipiec", 8: "Sierpień", 9: "Wrzesień", 10: "Październik", 11: "Listopad", 12: "Grudzień"
    }
    rok, miesiac, _ = map(int, data_wystawienia.split('-'))
    return f"{miesiace_polskie[miesiac]} {rok}"
# K_24_005506

# Funkcja do wyciągania miesiąca rozliczeniowego dla korekty na podstawie faktury
def get_miesiac_z_faktury_korygowanej(dokument_korygowany, all_invoices):
    normalized_dokument = normalize_invoice_number(dokument_korygowany)

    for invoice in all_invoices:
        normalized_invoice_number = normalize_invoice_number(invoice["Numer faktury"])

        if normalized_dokument in normalized_invoice_number:
            return get_rozliczeniowy_miesiac(invoice["Data wystawienia"])

    return "Brak danych"


# Normalizujemy numery faktur do porównań (usuwanie znaków specjalnych)
def normalize_invoice_number(invoice_number):
    return re.sub(r'[^A-Za-z0-9]', '', invoice_number).upper()


# Główne wywołanie
folder_path = "attachments"
template_path = "template.html"
output_path = "index.html"

fv_files = find_files_with_prefix(folder_path)
all_invoices = []
generate_html_from_template(folder_path, fv_files, template_path, output_path, all_invoices)
