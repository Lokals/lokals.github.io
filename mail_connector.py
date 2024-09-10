import imaplib
import email
from email.header import decode_header
import os


# Funkcja do logowania do serwera IMAP
def login_to_email(username, password, imap_server):
    mail = imaplib.IMAP4_SSL(imap_server)
    mail.login(username, password)
    return mail


# Funkcja do wyciągania listy plików z lokalnego folderu
def get_local_files(folder_path):
    if not os.path.exists(folder_path):
        os.makedirs(folder_path)  # Tworzenie folderu, jeśli nie istnieje
    return set(os.listdir(folder_path))


# Funkcja do pobierania załączników
def download_attachments(mail, folder="INBOX", download_folder="attachments"):
    mail.select(folder)

    # Pobierz identyfikatory wszystkich wiadomości
    status, messages = mail.search(None, 'ALL')

    mail_ids = messages[0].split()

    # Pobierz listę plików już znajdujących się w lokalnym folderze
    local_files = get_local_files(download_folder)

    # Iterowanie po wszystkich wiadomościach
    for mail_id in mail_ids:
        status, msg_data = mail.fetch(mail_id, '(RFC822)')
        for response_part in msg_data:
            if isinstance(response_part, tuple):
                msg = email.message_from_bytes(response_part[1])
                subject, encoding = decode_header(msg["Subject"])[0]
                if isinstance(subject, bytes):
                    subject = subject.decode(encoding if encoding else "utf-8")
                from_ = msg.get("From")
                print(f"Pobieram wiadomość od {from_} z tematem: {subject}")

                # Sprawdzanie załączników
                if msg.is_multipart():
                    for part in msg.walk():
                        if part.get_content_disposition() == "attachment":
                            filename = part.get_filename()
                            if filename:
                                # Dekodowanie nazwy pliku, jeśli to konieczne
                                filename, encoding = decode_header(filename)[0]
                                if isinstance(filename, bytes):
                                    filename = filename.decode(encoding if encoding else "utf-8")

                                # Sprawdzenie, czy plik już istnieje w lokalnym folderze
                                if filename in local_files:
                                    print(f"Załącznik {filename} już istnieje w folderze. Pomijam.")
                                    continue

                                # Pobierz załącznik, jeśli go jeszcze nie ma
                                filepath = os.path.join(download_folder, filename)
                                with open(filepath, "wb") as f:
                                    f.write(part.get_payload(decode=True))
                                print(f"Pobrano załącznik: {filename}")


# Dane logowania
username = "biuro_elk@op.pl"
password = "Bonieckibiuro1"
imap_server = "imap.poczta.onet.pl"

# Logowanie do skrzynki
mail = login_to_email(username, password, imap_server)

# Pobieranie załączników do lokalnego folderu 'attachments'
download_attachments(mail, download_folder="attachments")

# Wylogowanie z serwera
mail.logout()
