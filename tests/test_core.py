"""
Bateria de Testes Automatizados para os Módulos Centrais do Joplin UT
Valida:
1. Parsing e Serialização dos arquivos .md do Joplin
2. Esquema SQLite e buscas locais
3. Parsing de XML WebDAV (PROPFIND)
"""

import sys
import os
import unittest
from pathlib import Path

# Adiciona o diretório src ao path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from joplin_parser import (
    parse_joplin_file,
    serialize_joplin_note,
    serialize_joplin_folder,
    render_markdown_to_html,
    toggle_markdown_checkbox,
    TYPE_NOTE,
    TYPE_FOLDER
)
from webdav import WebDAVClient
import db

class TestJoplinCore(unittest.TestCase):

    def test_note_serialization_and_parsing(self):
        """Valida se uma nota serializada é perfeitamente interpretada pelo parser."""
        note_id = "a1b2c3d4e5f60718293a4b5c6d7e8f90"
        parent_id = "11223344556677889900aabbccddeeff"
        title = "Minha Primeira Nota no Ubuntu Touch"
        body = "Texto com **Markdown** e itens:\n- Item 1\n- Item 2"

        serialized = serialize_joplin_note(
            note_id=note_id,
            parent_id=parent_id,
            title=title,
            body=body,
            is_todo=0
        )

        parsed = parse_joplin_file(serialized)
        self.assertEqual(parsed["title"], title)
        self.assertEqual(parsed["body"], body)
        self.assertEqual(parsed["metadata"]["id"], note_id)
        self.assertEqual(parsed["metadata"]["parent_id"], parent_id)
        self.assertEqual(parsed["metadata"]["type_"], TYPE_NOTE)
        self.assertEqual(parsed["metadata"]["encryption_applied"], 0)

    def test_folder_serialization_and_parsing(self):
        """Valida se um caderno serializado é perfeitamente interpretado pelo parser."""
        folder_id = "f0f0f0f0f0f0f0f0f0f0f0f0f0f0f0f0"
        title = "Projetos 2026"

        serialized = serialize_joplin_folder(
            folder_id=folder_id,
            title=title
        )

        parsed = parse_joplin_file(serialized)
        self.assertEqual(parsed["title"], title)
        self.assertEqual(parsed["body"], "")
        self.assertEqual(parsed["metadata"]["id"], folder_id)
        self.assertEqual(parsed["metadata"]["type_"], TYPE_FOLDER)

    def test_webdav_propfind_xml_parsing(self):
        """Valida a interpretação do XML retornado pelo Nextcloud."""
        xml_sample = b"""<?xml version="1.0" encoding="UTF-8"?>
        <d:multistatus xmlns:d="DAV:">
            <d:response>
                <d:href>/remote.php/dav/files/braga/Joplin/</d:href>
                <d:propstat>
                    <d:prop>
                        <d:resourcetype><d:collection/></d:resourcetype>
                    </d:prop>
                </d:propstat>
            </d:response>
            <d:response>
                <d:href>/remote.php/dav/files/braga/Joplin/8f31b20e0b3c4f6eb8b758da4f4b232b.md</d:href>
                <d:propstat>
                    <d:prop>
                        <d:getetag>&quot;12345abcdef&quot;</d:getetag>
                        <d:getlastmodified>Sun, 26 Oct 2026 12:00:00 GMT</d:getlastmodified>
                        <d:resourcetype/>
                    </d:prop>
                </d:propstat>
            </d:response>
        </d:multistatus>"""

        client = WebDAVClient("https://example.com", "user", "pass", "Joplin")
        files = client._parse_propfind_xml(xml_sample)

        self.assertEqual(len(files), 1)
        self.assertEqual(files[0]["filename"], "8f31b20e0b3c4f6eb8b758da4f4b232b.md")
        self.assertEqual(files[0]["etag"], "12345abcdef")
        self.assertFalse(files[0]["is_dir"])

    def test_markdown_html_rendering_and_checklists(self):
        """Valida a renderização de Markdown rico com sublistas Tab e checklists clicáveis."""
        sample_md = (
            "# Estratégica\n"
            "## Pauta\n"
            "- ITI\n"
            "\t- Subitem 1\n"
            "\t\t- [ ] Tarefa pendente\n"
            "\t\t- [x] Tarefa concluída\n"
            "Link: [Portal](https://example.org) e ![anexo.png](:/4c211c3589204fe89d66900d265c69c0)"
        )
        rendered = render_markdown_to_html(sample_md)
        self.assertIn("Estratégica", rendered)
        self.assertIn('href="checkbox://4"', rendered)
        self.assertIn('href="checkbox://5"', rendered)
        self.assertIn('href="https://example.org"', rendered)
        self.assertIn("📎 anexo.png", rendered)

        # Alterna a linha 4 de [ ] para [x]
        updated_md, changed = toggle_markdown_checkbox(sample_md, 4)
        self.assertTrue(changed)
        self.assertIn("\t\t- [x] Tarefa pendente", updated_md)

        # Alterna novamente a linha 4 de [x] para [ ]
        reverted_md, changed2 = toggle_markdown_checkbox(updated_md, 4)
        self.assertTrue(changed2)
        self.assertIn("\t\t- [ ] Tarefa pendente", reverted_md)

    def test_openstore_package_and_policy_validation(self):
        """Valida manifesto Click, política AppArmor 2404.1, ícone e permissões OpenStore."""
        import json
        import subprocess
        root_dir = Path(__file__).parent.parent

        manifest = json.loads((root_dir / "manifest.json").read_text(encoding="utf-8"))
        self.assertEqual(manifest["name"], "joplin-ut.braga")
        self.assertEqual(manifest["architecture"], "all")
        self.assertEqual(manifest["framework"], "ubuntu-touch-24.04-1.x")
        self.assertIn("joplin-ut", manifest["hooks"])

        apparmor = json.loads((root_dir / "joplin-ut.apparmor").read_text(encoding="utf-8"))
        self.assertEqual(apparmor["policy_version"], 2404.1)
        allowed_groups = {"networking", "connectivity", "content_exchange", "content_exchange_source"}
        self.assertTrue(set(apparmor["policy_groups"]).issubset(allowed_groups))

        self.assertTrue((root_dir / "assets" / "logo.svg").exists())
        self.assertTrue((root_dir / "assets" / "logo-512.png").exists())
        self.assertTrue((root_dir / "store" / "screenshots" / "01-notes-list.png").exists())

        click_files = list((root_dir / "build" / "all" / "app").glob("*.click"))
        if click_files:
            out = subprocess.check_output(["dpkg-deb", "-c", str(click_files[0])], text=True)
            self.assertNotIn("__pycache__", out)
            for line in out.splitlines():
                if line.strip():
                    perms = line.split()[0]
                    # Nenhum arquivo no pacote Click pode ter permissão de escrita global (o+w)
                    self.assertNotEqual(perms[8], "w", f"Permissão world-writable detectada: {line}")

if __name__ == "__main__":
    unittest.main()
