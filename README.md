# Joplin UT (Ubuntu Touch Joplin & Nextcloud Client)

Cliente nativo de notas para **Ubuntu Touch (Lomiri)**, integrado a servidores **Nextcloud** via **WebDAV** utilizando a estrutura de sincronização e metadados de texto plano do **Joplin** (`encryption_applied: 0`).

Desenvolvido para arquitetura `arm64` (testado e homologado no **Xiaomi Poco X3 NFC** rodando **Ubuntu Touch 24.04-2.x Noble Numbat**).

---

## 🚀 Como Executar em um Novo Computador

### 1. Pré-requisitos
- **Ubuntu Linux** (ou distribuição com suporte a Snap/LXD/Docker)
- **Clickable 7.x** instalado:
  ```bash
  sudo snap install clickable --classic
  sudo snap connect clickable:ssh-keys
  sudo snap connect clickable:etc-gitconfig
  ```
- **ADB** (Android Debug Bridge):
  ```bash
  sudo apt install adb
  ```
- **Python 3.10+** (para rodar testes locais):
  ```bash
  python3 --version
  ```

### 2. Conectar o Dispositivo Ubuntu Touch via USB
1. Conecte o aparelho via cabo USB.
2. Ative a Depuração USB no aparelho em *Configurações do Sistema > Sobre o Telefone > Modo Desenvolvedor*.
3. Verifique a autorização no terminal:
   ```bash
   adb devices
   ```
   *(Deve retornar `7e90aed3 device` ou similar)*.

### 3. Compilar, Instalar e Executar
No diretório raiz deste projeto:
```bash
clickable --arch all
```
> **Nota de Arquitetura**: Como o aplicativo é construído inteiramente em **QML** e **Python puro** com **PyOtherSide**, a arquitetura Click configurada é `"all"` (não necessita de compilador C++ cruzado, instalando de forma ultra-rápida no dispositivo).

Para apenas relançar o aplicativo já instalado:
```bash
clickable launch --arch all
```

Para acompanhar os logs do app em tempo real:
```bash
clickable logs
# ou via adb:
adb shell "journalctl --user -f | grep -E 'joplin|Main|main'"
```

### 4. Rodar Testes Unitários
Para validar os motores de parser de metadados Joplin e cliente WebDAV sem precisar do telefone:
```bash
python3 tests/test_core.py
```

---

## 📁 Estrutura de Diretórios do Projeto

```text
2026_joplin_UT/
├── CMakeLists.txt              # Script CMake de instalação dos componentes
├── clickable.json              # Configuração Clickable 7.0 (compatibilidade)
├── clickable.yaml              # Configuração Clickable 7.0 principal
├── manifest.json.in            # Manifesto do pacote Click (versão, hooks, apparmor)
├── manifest.json               # Manifesto gerado para leitura do Clickable
├── joplin-ut.apparmor          # Política de segurança AppArmor (política 2404.1)
├── joplin-ut.desktop.in        # Lançador do Lomiri no Ubuntu Touch
├── assets/
│   └── logo.svg                # Ícone vetorial do aplicativo (SVG)
├── qml/                        # Interface Gráfica Lomiri
│   ├── Main.qml                # Janela principal, inicializador PyOtherSide e Drawer
│   ├── components/
│   │   └── NotebookDrawer.qml  # Gaveta lateral com árvore hierárquica de cadernos
│   └── pages/
│       ├── NotesListPage.qml   # Lista de notas, busca, ordenação nativa (ListModel)
│       ├── NoteEditPage.qml    # Editor de notas e prévia Markdown
│       └── SettingsPage.qml    # Configurações WebDAV Nextcloud e teste de conexão
├── src/                        # Backend Python 3 (Offline-First)
│   ├── __init__.py             # Versão do pacote Python
│   ├── config.py               # Gerenciador de configurações em ~/.config/joplin-ut.braga/
│   ├── db.py                   # Banco SQLite local em ~/.local/share/joplin-ut.braga/
│   ├── joplin_parser.py        # Serializador e analisador de arquivos .md do Joplin
│   ├── webdav.py               # Cliente HTTP/WebDAV (Basic Auth, PROPFIND, GET, PUT)
│   ├── sync.py                 # Motor de sincronização bidirecional
│   └── main.py                 # Ponto de entrada chamado pelo QML via PyOtherSide
├── tests/
│   └── test_core.py            # Testes unitários do parser e WebDAV
├── DEVELOPMENT_HANDOVER.md     # Documento técnico completo de continuidade
└── README.md                   # Este arquivo
```

---

## 🔒 Confinamento AppArmor & Diretórios no Dispositivo

Conforme as regras do Ubuntu Touch 24.04 (Noble), o app possui confinamento estrito:
- **Configurações**: `/home/phablet/.config/joplin-ut.braga/settings.json`
- **Banco de Dados Local**: `/home/phablet/.local/share/joplin-ut.braga/joplin_local.db`
- **Permissões Ativas** (`joplin-ut.apparmor`):
  - `networking`: Acesso à internet via Wi-Fi/dados móveis para falar com o Nextcloud.
  - `connectivity`: Monitoramento do estado da conexão.
  - `content_exchange` e `content_exchange_source`: Compartilhamento de notas via Content Hub.

---

## 🛠️ Tecnologias Utilizadas
- **UI Toolkit**: Lomiri Components 1.3 / QtQuick 2.12 (QML)
- **Ponte QML/Python**: PyOtherSide 1.5 (`io.thp.pyotherside`)
- **Linguagem Backend**: Python 3.10+
- **Banco de Dados**: SQLite3 (armazenamento local offline-first)
- **Protocolo de Rede**: WebDAV (HTTP/HTTPS com urllib nativo sem dependências C externas)
- **Formato das Notas**: Markdown com cabeçalho/rodapé de metadados padrão Joplin (`UUID.md`)
