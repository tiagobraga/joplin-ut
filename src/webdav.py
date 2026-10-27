"""
Cliente WebDAV para Nextcloud no Joplin UT
Utiliza estritamente bibliotecas padrão do Python (urllib e xml.etree).
"""

import base64
import urllib.request
import urllib.error
import urllib.parse
import xml.etree.ElementTree as ET
from typing import List, Dict, Any, Optional, Tuple

class WebDAVClient:
    def __init__(self, server_url: str, username: str, password: str, joplin_folder: str = "Joplin"):
        self.server_url = server_url.rstrip("/")
        self.username = username
        self.password = password
        self.joplin_folder = joplin_folder.strip("/")

        # Monta a URL base do WebDAV do Nextcloud
        # Se a URL fornecida já contém remote.php/dav, usa como base
        if "remote.php" in self.server_url:
            self.base_url = f"{self.server_url}/{self.joplin_folder}"
        else:
            self.base_url = f"{self.server_url}/remote.php/dav/files/{urllib.parse.quote(self.username)}/{self.joplin_folder}"

    def _get_headers(self) -> Dict[str, str]:
        auth_str = f"{self.username}:{self.password}"
        encoded_auth = base64.b64encode(auth_str.encode("utf-8")).decode("ascii")
        return {
            "Authorization": f"Basic {encoded_auth}",
            "User-Agent": "Joplin-UT/1.0.0 (Ubuntu Touch)"
        }

    def test_connection(self) -> Tuple[bool, str]:
        """Testa se as credenciais e a URL do servidor estão válidas."""
        headers = self._get_headers()
        headers["Depth"] = "0"
        
        req = urllib.request.Request(self.base_url, headers=headers, method="PROPFIND")
        try:
            with urllib.request.urlopen(req, timeout=15) as response:
                if response.status in (200, 207):
                    return True, "Conexão estabelecida com sucesso!"
                return False, f"Servidor retornou status HTTP {response.status}"
        except urllib.error.HTTPError as e:
            if e.code == 401:
                return False, "Usuário ou senha inválidos no Nextcloud."
            elif e.code == 404:
                return False, f"Pasta '{self.joplin_folder}' não foi encontrada no Nextcloud."
            return False, f"Erro HTTP {e.code}: {e.reason}"
        except Exception as e:
            return False, f"Falha ao conectar: {str(e)}"

    def list_files(self) -> List[Dict[str, Any]]:
        """
        Executa PROPFIND com Depth: 1 para listar todos os arquivos na pasta Joplin.
        Retorna lista de dicionários com nome, href, etag e last_modified.
        """
        headers = self._get_headers()
        headers["Depth"] = "1"
        headers["Content-Type"] = "application/xml; charset=utf-8"

        body = (
            '<?xml version="1.0" encoding="utf-8" ?>\n'
            '<d:propfind xmlns:d="DAV:">\n'
            '  <d:prop>\n'
            '    <d:getetag />\n'
            '    <d:getlastmodified />\n'
            '    <d:resourcetype />\n'
            '  </d:prop>\n'
            '</d:propfind>'
        ).encode("utf-8")

        req = urllib.request.Request(self.base_url, data=body, headers=headers, method="PROPFIND")
        try:
            with urllib.request.urlopen(req, timeout=30) as response:
                xml_data = response.read()
                return self._parse_propfind_xml(xml_data)
        except Exception as e:
            print(f"[WebDAV] Erro ao listar arquivos: {e}")
            raise e

    def _parse_propfind_xml(self, xml_bytes: bytes) -> List[Dict[str, Any]]:
        """Interpreta o XML retornado pelo Nextcloud."""
        root = ET.fromstring(xml_bytes)
        
        # Mapeamento do namespace WebDAV
        ns = {"d": "DAV:"}
        results = []

        for resp in root.findall("d:response", ns):
            href_el = resp.find("d:href", ns)
            if href_el is None or href_el.text is None:
                continue
            
            raw_href = urllib.parse.unquote(href_el.text)
            filename = raw_href.rstrip("/").split("/")[-1]

            # Ignora a própria pasta raiz
            if not filename or filename == self.joplin_folder:
                continue

            etag_el = resp.find(".//d:getetag", ns)
            etag = etag_el.text.strip('"') if etag_el is not None and etag_el.text else ""

            lm_el = resp.find(".//d:getlastmodified", ns)
            last_modified = lm_el.text if lm_el is not None and lm_el.text else ""

            is_dir = resp.find(".//d:resourcetype/d:collection", ns) is not None

            results.append({
                "filename": filename,
                "href": raw_href,
                "etag": etag,
                "last_modified": last_modified,
                "is_dir": is_dir
            })

        return results

    def get_file_content(self, filename: str) -> Tuple[str, str]:
        """
        Baixa o conteúdo de texto de um arquivo .md do Joplin.
        Retorna (conteúdo_str, etag).
        """
        file_url = f"{self.base_url}/{urllib.parse.quote(filename)}"
        req = urllib.request.Request(file_url, headers=self._get_headers(), method="GET")

        with urllib.request.urlopen(req, timeout=20) as response:
            content = response.read().decode("utf-8", errors="replace")
            etag = response.headers.get("ETag", "").strip('"')
            return content, etag

    def unlock_file(self, filename: str) -> bool:
        """Remove bloqueio (files_lock / Text) de um arquivo no Nextcloud via WebDAV UNLOCK."""
        file_url = f"{self.base_url}/{urllib.parse.quote(filename)}"
        headers = self._get_headers()
        headers["X-User-Lock"] = "1"
        req = urllib.request.Request(file_url, headers=headers, method="UNLOCK")
        try:
            with urllib.request.urlopen(req, timeout=15) as response:
                return response.status in (200, 204)
        except Exception as e:
            print(f"[WebDAV] Aviso ao desbloquear {filename}: {e}")
            return False

    def put_file_content(self, filename: str, content: str) -> str:
        """
        Envia o arquivo serializado para o Nextcloud via PUT.
        Retorna o novo ETag se fornecido pelo servidor.
        """
        file_url = f"{self.base_url}/{urllib.parse.quote(filename)}"
        data = content.encode("utf-8")
        headers = self._get_headers()
        headers["Content-Type"] = "text/markdown; charset=utf-8"

        req = urllib.request.Request(file_url, data=data, headers=headers, method="PUT")
        try:
            with urllib.request.urlopen(req, timeout=20) as response:
                etag = response.headers.get("ETag") or response.headers.get("OC-ETag") or ""
                return etag.strip('"')
        except urllib.error.HTTPError as e:
            if e.code == 423 and self.unlock_file(filename):
                req_retry = urllib.request.Request(file_url, data=data, headers=headers, method="PUT")
                with urllib.request.urlopen(req_retry, timeout=20) as response:
                    etag = response.headers.get("ETag") or response.headers.get("OC-ETag") or ""
                    return etag.strip('"')
            raise e

    def delete_file(self, filename: str) -> bool:
        """Deleta um arquivo do Nextcloud."""
        file_url = f"{self.base_url}/{urllib.parse.quote(filename)}"
        req = urllib.request.Request(file_url, headers=self._get_headers(), method="DELETE")
        try:
            with urllib.request.urlopen(req, timeout=15) as response:
                return response.status in (200, 204)
        except urllib.error.HTTPError as e:
            if e.code == 404:
                return True
            if e.code == 423 and self.unlock_file(filename):
                req_retry = urllib.request.Request(file_url, headers=self._get_headers(), method="DELETE")
                with urllib.request.urlopen(req_retry, timeout=15) as response:
                    return response.status in (200, 204)
            raise e
