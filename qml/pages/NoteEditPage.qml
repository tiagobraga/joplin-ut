import QtQuick 2.12
import Lomiri.Components 1.3
import Lomiri.Components.Popups 1.3

Page {
    id: noteEditPage
    title: isNewNote ? "Nova Nota" : (isPreviewMode ? "Visualizar Nota" : "Editar Nota")

    property string noteId: ""
    property string folderId: ""
    property string folderTitle: "Sem Caderno"
    property var foldersList: []
    property var allTagsList: []
    property var noteTagsList: []
    property bool isNewNote: noteId === ""
    property bool isPreviewMode: !isNewNote
    property bool isSaving: false
    property bool isLoaded: false
    property bool hasUnsavedChanges: false
    property int noteDirty: 0
    property string noteUpdatedDisplay: ""
    property string renderedHtml: ""
    property string previousBodyText: ""
    property bool isAutoContinuingList: false

    signal noteSaved()
    signal noteDeleted()
    signal tagsUpdated()

    function isTagAttached(tagId) {
        if (!noteTagsList || !tagId) return false;
        var target = String(tagId);
        for (var i = 0; i < noteTagsList.length; i++) {
            if (noteTagsList[i] && String(noteTagsList[i].id) === target) {
                return true;
            }
        }
        return false;
    }

    function openTagsManager() {
        if (noteEditPage.isNewNote) {
            var title = titleField.text.trim() || "Sem Título";
            titleField.text = title;
            py.call('main.save_note_content', [
                "",
                noteEditPage.folderId || "",
                title,
                bodyField.text || ""
            ], function(res) {
                if (res && res.success) {
                    noteEditPage.noteId = res.id || "";
                    noteEditPage.isNewNote = false;
                    noteEditPage.hasUnsavedChanges = false;
                    noteEditPage.noteDirty = 1;
                    noteEditPage.noteSaved();
                    PopupUtils.open(noteTagsDialog);
                }
            });
        } else {
            PopupUtils.open(noteTagsDialog);
        }
    }

    header: PageHeader {
        id: editHeader
        title: noteEditPage.title

        leadingActionBar.actions: [
            Action {
                iconName: "back"
                text: "Voltar"
                onTriggered: {
                    if (noteEditPage.hasUnsavedChanges) {
                        noteEditPage.saveNote(true);
                    } else {
                        pageStack.pop();
                    }
                }
            }
        ]

        trailingActionBar.actions: [
            Action {
                iconName: noteEditPage.isPreviewMode ? "edit" : "view-on"
                text: noteEditPage.isPreviewMode ? "Editar" : "Visualizar"
                onTriggered: {
                    if (noteEditPage.isPreviewMode) {
                        noteEditPage.isPreviewMode = false;
                    } else {
                        // Ao voltar do modo edição para visualização, salva alterações locais se houver
                        if (noteEditPage.hasUnsavedChanges) {
                            noteEditPage.saveNote(false);
                        } else {
                            noteEditPage.refreshPreviewHtml();
                            noteEditPage.isPreviewMode = true;
                        }
                    }
                }
            },
            Action {
                iconName: "save"
                text: "Salvar"
                onTriggered: noteEditPage.saveNote(true)
            },
            Action {
                iconName: "edit-copy"
                text: "Copiar"
                onTriggered: {
                    var fullCopy = (titleField.text || "") + "\n\n" + (bodyField.text || "");
                    Clipboard.push(fullCopy);
                }
            },
            Action {
                iconName: "delete"
                text: "Excluir"
                visible: !noteEditPage.isNewNote
                onTriggered: {
                    PopupUtils.open(deleteConfirmDialog);
                }
            }
        ]
    }

    Component {
        id: moveFolderDialog
        Dialog {
            id: moveDlg
            title: "Mover para Caderno"
            text: "Selecione o caderno de destino desta nota:"

            Flickable {
                width: parent.width
                height: Math.min(units.gu(34), moveCol.height)
                contentHeight: moveCol.height
                clip: true

                Column {
                    id: moveCol
                    width: parent.width
                    spacing: units.gu(0.5)

                    Repeater {
                        model: noteEditPage.foldersList || []
                        delegate: Button {
                            width: moveCol.width
                            height: units.gu(4.6)
                            text: (modelData.display_title || modelData.title || "Sem Nome")
                            color: String(modelData.id) === noteEditPage.folderId ? "#1B5EBF" : LomiriColors.porcelain
                            onClicked: {
                                var targetId = String(modelData.id || "");
                                var targetTitle = String(modelData.title || "Sem Nome");
                                PopupUtils.close(moveDlg);
                                if (targetId === noteEditPage.folderId) return;
                                noteEditPage.folderId = targetId;
                                noteEditPage.folderTitle = targetTitle;
                                if (!noteEditPage.isNewNote) {
                                    py.call('main.move_note_to_folder', [
                                        noteEditPage.noteId || "",
                                        targetId,
                                        titleField.text || "",
                                        bodyField.text || ""
                                    ], function(res) {
                                        if (res && res.success) {
                                            noteEditPage.noteDirty = 1;
                                            if (res.folder_title) {
                                                noteEditPage.folderTitle = res.folder_title;
                                            }
                                            if (res.updated_display) {
                                                noteEditPage.noteUpdatedDisplay = res.updated_display;
                                            }
                                            noteEditPage.noteSaved();
                                        }
                                    });
                                } else {
                                    noteEditPage.hasUnsavedChanges = true;
                                }
                            }
                        }
                    }
                }
            }

            Button {
                text: "Cancelar"
                onClicked: PopupUtils.close(moveDlg)
            }
        }
    }

    Component {
        id: noteTagsDialog
        Dialog {
            id: tagsDlg
            title: "Etiquetas (Tags) da Nota"
            text: "Toque para marcar/desmarcar ou crie uma nova tag:"

            Row {
                width: parent.width
                spacing: units.gu(1)

                TextField {
                    id: newTagInNoteField
                    width: parent.width - addTagBtn.width - units.gu(1)
                    placeholderText: "Nova tag (ex: urgente)"
                }

                Button {
                    id: addTagBtn
                    width: units.gu(9)
                    text: "+ Criar"
                    color: LomiriColors.orange
                    enabled: newTagInNoteField.text.trim().length > 0
                    onClicked: {
                        var tagName = newTagInNoteField.text.trim();
                        newTagInNoteField.text = "";
                        py.call('main.create_tag', [tagName, noteEditPage.noteId || ""], function(res) {
                            if (res && res.success) {
                                noteEditPage.noteTagsList = res.note_tags || [];
                                py.call('main.get_tags_list', [], function(allT) {
                                    noteEditPage.allTagsList = allT || [];
                                    noteEditPage.tagsUpdated();
                                });
                            }
                        });
                    }
                }
            }

            Flickable {
                width: parent.width
                height: Math.min(units.gu(28), tagsCol.height)
                contentHeight: tagsCol.height
                clip: true

                Column {
                    id: tagsCol
                    width: parent.width
                    spacing: units.gu(0.5)

                    Repeater {
                        model: noteEditPage.allTagsList || []
                        delegate: Button {
                            width: tagsCol.width
                            height: units.gu(4.5)
                            property bool attached: noteEditPage.isTagAttached(modelData.id)
                            text: (attached ? "☑ #" : "☐ #") + (modelData.title || "tag")
                            color: attached ? "#1B5EBF" : LomiriColors.porcelain
                            onClicked: {
                                var tId = String(modelData.id || "");
                                py.call('main.toggle_note_tag', [noteEditPage.noteId || "", tId], function(res) {
                                    if (res && res.success) {
                                        noteEditPage.noteTagsList = res.note_tags || [];
                                        noteEditPage.tagsUpdated();
                                    }
                                });
                            }
                        }
                    }
                }
            }

            Button {
                text: "Concluir"
                color: "#1B5EBF"
                onClicked: PopupUtils.close(tagsDlg)
            }
        }
    }

    Component {
        id: deleteConfirmDialog
        Dialog {
            id: dialog
            title: "Excluir Nota"
            text: "Deseja realmente excluir esta nota? A exclusão será enviada ao Nextcloud na próxima sincronização."
            Button {
                text: "Cancelar"
                onClicked: PopupUtils.close(dialog)
            }
            Button {
                text: "Excluir"
                color: LomiriColors.red
                onClicked: {
                    PopupUtils.close(dialog);
                    py.call('main.delete_single_note', [noteEditPage.noteId || ""], function(res) {
                        noteEditPage.noteDeleted();
                        pageStack.pop();
                    });
                }
            }
        }
    }

    function refreshPreviewHtml() {
        var currentBody = bodyField.text || "";
        py.call('main.render_note_preview', [currentBody], function(htmlResult) {
            noteEditPage.renderedHtml = htmlResult || "";
        });
    }

    function saveNote(closeAfterSave) {
        if (isSaving) return;
        var title = titleField.text.trim();
        var body = bodyField.text;

        if (title.length === 0 && body.trim().length === 0) {
            if (closeAfterSave) {
                pageStack.pop();
            }
            return;
        }
        if (title.length === 0) {
            title = "Sem Título";
            titleField.text = title;
        }

        isSaving = true;
        py.call('main.save_note_content', [
            noteEditPage.noteId || "",
            noteEditPage.folderId || "",
            title,
            body
        ], function(result) {
            isSaving = false;
            if (result && result.success) {
                noteEditPage.noteId = result.id || noteEditPage.noteId;
                noteEditPage.isNewNote = false;
                noteEditPage.hasUnsavedChanges = false;
                noteEditPage.noteDirty = 1;
                if (result.folder_title) {
                    noteEditPage.folderTitle = result.folder_title;
                }
                if (result.updated_display) {
                    noteEditPage.noteUpdatedDisplay = result.updated_display;
                }
                if (result.rendered_html !== undefined) {
                    noteEditPage.renderedHtml = result.rendered_html;
                }
                noteEditPage.noteSaved();
                if (closeAfterSave) {
                    pageStack.pop();
                } else {
                    noteEditPage.isPreviewMode = true;
                }
            }
        });
    }

    function handleCheckboxToggle(lineIndex) {
        var savedScrollY = previewContainer.contentY;
        var currentTitle = titleField.text.trim() || "Sem Título";
        var currentBody = bodyField.text || "";

        py.call('main.toggle_note_checkbox', [
            noteEditPage.noteId || "",
            noteEditPage.folderId || "",
            currentTitle,
            currentBody,
            lineIndex
        ], function(res) {
            if (res && res.success && res.changed) {
                noteEditPage.isLoaded = false;
                bodyField.text = res.body || "";
                noteEditPage.previousBodyText = bodyField.text;
                noteEditPage.isLoaded = true;
                noteEditPage.hasUnsavedChanges = false;
                noteEditPage.noteDirty = 1;
                if (res.updated_display) {
                    noteEditPage.noteUpdatedDisplay = res.updated_display;
                }
                if (res.rendered_html !== undefined) {
                    noteEditPage.renderedHtml = res.rendered_html;
                }
                previewContainer.contentY = savedScrollY;
                noteEditPage.noteSaved();
            }
        });
    }

    function insertMarkdownSnippet(prefix, suffix) {
        var start = bodyField.selectionStart;
        var end = bodyField.selectionEnd;
        var fullText = bodyField.text || "";
        var selected = fullText.substring(start, end);
        var replacement = prefix + (selected.length > 0 ? selected : "") + (suffix || "");
        noteEditPage.isAutoContinuingList = true;
        bodyField.remove(start, end);
        bodyField.insert(start, replacement);
        noteEditPage.previousBodyText = bodyField.text;
        noteEditPage.isAutoContinuingList = false;
        bodyField.forceActiveFocus();
        bodyField.cursorPosition = start + prefix.length + selected.length;
    }

    // Insere item de lista ou tarefa preservando o recuo (Tabs) da linha atual
    function insertListItem(marker) {
        var fullText = bodyField.text || "";
        var pos = bodyField.cursorPosition;
        var lineStart = fullText.lastIndexOf("\n", Math.max(0, pos - 1)) + 1;
        if (pos === 0) lineStart = 0;
        var currentLine = fullText.substring(lineStart, pos);
        var indentMatch = currentLine.match(/^(\t+)/);
        var indent = indentMatch ? indentMatch[1] : "";
        var needsNewline = (pos > 0 && fullText.charAt(pos - 1) !== "\n" && currentLine.trim().length > 0);
        var snippet = (needsNewline ? "\n" + indent : "") + marker;
        noteEditPage.isAutoContinuingList = true;
        bodyField.insert(pos, snippet);
        noteEditPage.previousBodyText = bodyField.text;
        noteEditPage.isAutoContinuingList = false;
        bodyField.forceActiveFocus();
        bodyField.cursorPosition = pos + snippet.length;
    }

    // Aumenta o recuo (adiciona \t no início da linha atual)
    function indentCurrentLine() {
        var fullText = bodyField.text || "";
        var pos = bodyField.cursorPosition;
        var lineStart = fullText.lastIndexOf("\n", Math.max(0, pos - 1)) + 1;
        if (pos === 0) lineStart = 0;
        noteEditPage.isAutoContinuingList = true;
        bodyField.insert(lineStart, "\t");
        noteEditPage.previousBodyText = bodyField.text;
        noteEditPage.isAutoContinuingList = false;
        bodyField.forceActiveFocus();
        bodyField.cursorPosition = pos + 1;
    }

    // Diminui o recuo (remove \t ou até 4 espaços do início da linha atual)
    function outdentCurrentLine() {
        var fullText = bodyField.text || "";
        var pos = bodyField.cursorPosition;
        var lineStart = fullText.lastIndexOf("\n", Math.max(0, pos - 1)) + 1;
        if (pos === 0) lineStart = 0;

        if (fullText.charAt(lineStart) === "\t") {
            noteEditPage.isAutoContinuingList = true;
            bodyField.remove(lineStart, lineStart + 1);
            noteEditPage.previousBodyText = bodyField.text;
            noteEditPage.isAutoContinuingList = false;
            bodyField.forceActiveFocus();
            bodyField.cursorPosition = Math.max(lineStart, pos - 1);
        } else {
            var removedSpaces = 0;
            while (removedSpaces < 4 && fullText.charAt(lineStart + removedSpaces) === " ") {
                removedSpaces++;
            }
            if (removedSpaces > 0) {
                noteEditPage.isAutoContinuingList = true;
                bodyField.remove(lineStart, lineStart + removedSpaces);
                noteEditPage.previousBodyText = bodyField.text;
                noteEditPage.isAutoContinuingList = false;
                bodyField.forceActiveFocus();
                bodyField.cursorPosition = Math.max(lineStart, pos - removedSpaces);
            } else {
                bodyField.forceActiveFocus();
            }
        }
    }

    // Continua automaticamente listas (- , * , + , 1. ) e checkboxes (- [ ] ) ao pressionar Enter
    function handleBodyEnterContinuation() {
        var textNow = bodyField.text || "";
        var pos = bodyField.cursorPosition;
        if (pos <= 0 || textNow.charAt(pos - 1) !== "\n") {
            noteEditPage.previousBodyText = textNow;
            return;
        }

        var nlPos = pos - 1;
        var prevLineStart = textNow.lastIndexOf("\n", Math.max(0, nlPos - 1)) + 1;
        if (nlPos === 0) prevLineStart = 0;
        var prevLine = textNow.substring(prevLineStart, nlPos);

        // 1. Checkbox com conteúdo: ex. "\t- [ ] Item" ou "- [x] Feito"
        var cbMatch = prevLine.match(/^([ \t]*[-*+]\s+)\[[ xX]\](\s+)(.*\S.*)$/);
        if (cbMatch) {
            var cbPrefix = cbMatch[1] + "[ ]" + cbMatch[2];
            noteEditPage.isAutoContinuingList = true;
            bodyField.insert(pos, cbPrefix);
            bodyField.cursorPosition = pos + cbPrefix.length;
            noteEditPage.previousBodyText = bodyField.text;
            noteEditPage.isAutoContinuingList = false;
            return;
        }

        // 2. Checkbox vazio: ex. "\t- [ ] " -> remove o marcador vazio ao dar Enter novamente
        var emptyCbMatch = prevLine.match(/^([ \t]*[-*+]\s+\[[ xX]\]\s*)$/);
        if (emptyCbMatch) {
            noteEditPage.isAutoContinuingList = true;
            bodyField.remove(prevLineStart, pos);
            bodyField.cursorPosition = prevLineStart;
            noteEditPage.previousBodyText = bodyField.text;
            noteEditPage.isAutoContinuingList = false;
            return;
        }

        // 3. Lista com marcadores com conteúdo: ex. "\t- Item" ou "* Tópico"
        var ulMatch = prevLine.match(/^([ \t]*[-*+]\s+)(.*\S.*)$/);
        if (ulMatch) {
            var ulPrefix = ulMatch[1];
            noteEditPage.isAutoContinuingList = true;
            bodyField.insert(pos, ulPrefix);
            bodyField.cursorPosition = pos + ulPrefix.length;
            noteEditPage.previousBodyText = bodyField.text;
            noteEditPage.isAutoContinuingList = false;
            return;
        }

        // 4. Lista com marcador vazio: ex. "\t- " -> remove o marcador vazio ao dar Enter novamente
        var emptyUlMatch = prevLine.match(/^([ \t]*[-*+][ \t]+)$/);
        if (emptyUlMatch) {
            noteEditPage.isAutoContinuingList = true;
            bodyField.remove(prevLineStart, pos);
            bodyField.cursorPosition = prevLineStart;
            noteEditPage.previousBodyText = bodyField.text;
            noteEditPage.isAutoContinuingList = false;
            return;
        }

        // 5. Lista numerada com conteúdo: ex. "\t1. Item"
        var olMatch = prevLine.match(/^([ \t]*)(\d+)(\.\s+)(.*\S.*)$/);
        if (olMatch) {
            var nextNum = parseInt(olMatch[2], 10) + 1;
            var olPrefix = olMatch[1] + String(nextNum) + olMatch[3];
            noteEditPage.isAutoContinuingList = true;
            bodyField.insert(pos, olPrefix);
            bodyField.cursorPosition = pos + olPrefix.length;
            noteEditPage.previousBodyText = bodyField.text;
            noteEditPage.isAutoContinuingList = false;
            return;
        }

        // 6. Lista numerada vazia: ex. "\t2. " -> remove o marcador vazio ao dar Enter novamente
        var emptyOlMatch = prevLine.match(/^([ \t]*\d+\.[ \t]+)$/);
        if (emptyOlMatch) {
            noteEditPage.isAutoContinuingList = true;
            bodyField.remove(prevLineStart, pos);
            bodyField.cursorPosition = prevLineStart;
            noteEditPage.previousBodyText = bodyField.text;
            noteEditPage.isAutoContinuingList = false;
            return;
        }
    }

    function ensureCursorVisible() {
        if (!bodyField.activeFocus) return;
        var cursorY = bodyField.cursorRectangle.y;
        var cursorH = bodyField.cursorRectangle.height;
        var viewTop = bodyFlickable.contentY;
        var viewBottom = viewTop + bodyFlickable.height - units.gu(3);

        if (cursorY < viewTop) {
            bodyFlickable.contentY = Math.max(0, cursorY - units.gu(2));
        } else if (cursorY + cursorH > viewBottom) {
            bodyFlickable.contentY = (cursorY + cursorH) - bodyFlickable.height + units.gu(4);
        }
    }

    // Conteúdo principal ajustado automaticamente para o Teclado Virtual (Maliit OSK)
    Item {
        id: mainArea
        anchors.top: editHeader.bottom
        anchors.left: parent.left
        anchors.right: parent.right
        anchors.bottom: parent.bottom
        anchors.bottomMargin: Qt.inputMethod.visible ? Qt.inputMethod.keyboardRectangle.height : 0

        // ==========================================
        // 1. MODO DE VISUALIZAÇÃO RICA (MARKDOWN)
        // ==========================================
        Flickable {
            id: previewContainer
            anchors.fill: parent
            anchors.margins: units.gu(2)
            visible: noteEditPage.isPreviewMode
            contentWidth: width
            contentHeight: previewCol.height + units.gu(6)
            clip: true

            Column {
                id: previewCol
                width: parent.width
                spacing: units.gu(1.2)

                // Título Principal da Nota
                Label {
                    text: titleField.text || "Sem Título"
                    fontSize: "x-large"
                    font.bold: true
                    wrapMode: Text.Wrap
                    width: parent.width
                    color: theme.palette.normal.baseText
                }

                // Barra de metadados, caderno atual (clicável para mover) e status de sincronização
                Row {
                    width: parent.width
                    spacing: units.gu(1)

                    Rectangle {
                        height: units.gu(3.2)
                        width: folderBadgeLabel.width + units.gu(2.0)
                        radius: units.gu(0.8)
                        color: folderBadgeMouse.pressed ? "#D0E0F8" : "#E8F0FE"
                        anchors.verticalCenter: parent.verticalCenter

                        Label {
                            id: folderBadgeLabel
                            anchors.centerIn: parent
                            text: "📁 " + (noteEditPage.folderTitle || "Sem Caderno") + " ▾"
                            fontSize: "small"
                            font.bold: true
                            color: "#1B5EBF"
                        }

                        MouseArea {
                            id: folderBadgeMouse
                            anchors.fill: parent
                            onClicked: PopupUtils.open(moveFolderDialog)
                        }
                    }

                    Rectangle {
                        height: units.gu(3.2)
                        width: tagsBadgeLabel.width + units.gu(2.0)
                        radius: units.gu(0.8)
                        color: tagsBadgeMouse.pressed ? "#FCE3D8" : "#FDEEE9"
                        anchors.verticalCenter: parent.verticalCenter

                        Label {
                            id: tagsBadgeLabel
                            anchors.centerIn: parent
                            text: "🏷️ Tags (" + (noteEditPage.noteTagsList ? noteEditPage.noteTagsList.length : 0) + ") ▾"
                            fontSize: "small"
                            font.bold: true
                            color: "#E95420"
                        }

                        MouseArea {
                            id: tagsBadgeMouse
                            anchors.fill: parent
                            onClicked: noteEditPage.openTagsManager()
                        }
                    }

                    Rectangle {
                        width: units.gu(1)
                        height: units.gu(1)
                        radius: width / 2
                        anchors.verticalCenter: parent.verticalCenter
                        color: noteEditPage.noteDirty === 1 ? LomiriColors.orange : LomiriColors.green
                    }

                    Label {
                        text: (noteEditPage.noteDirty === 1 ? "Pendente" : "Sincronizada") +
                              (noteEditPage.noteUpdatedDisplay ? " • " + noteEditPage.noteUpdatedDisplay : "")
                        fontSize: "small"
                        color: LomiriColors.slate
                        anchors.verticalCenter: parent.verticalCenter
                    }
                }

                // Pílulas de Tags ativas da nota
                Flow {
                    width: parent.width
                    spacing: units.gu(0.8)
                    visible: noteEditPage.noteTagsList && noteEditPage.noteTagsList.length > 0

                    Repeater {
                        model: noteEditPage.noteTagsList || []
                        delegate: Rectangle {
                            height: units.gu(2.8)
                            width: chipText.width + units.gu(1.6)
                            radius: units.gu(1.4)
                            color: "#F0F4F8"
                            border.color: "#D0E0F8"
                            border.width: units.dp(1)

                            Label {
                                id: chipText
                                anchors.centerIn: parent
                                text: "#" + (modelData.title || "tag")
                                fontSize: "small"
                                color: "#1B5EBF"
                            }

                            MouseArea {
                                anchors.fill: parent
                                onClicked: noteEditPage.openTagsManager()
                            }
                        }
                    }
                }

                Rectangle {
                    width: parent.width
                    height: units.dp(1)
                    color: theme.palette.normal.baseText
                    opacity: 0.15
                }

                // Corpo da nota renderizado em RichText HTML com suporte a Checklists e Links
                Text {
                    id: markdownViewer
                    width: parent.width
                    text: noteEditPage.renderedHtml || "<p style='color:#888888;'><i>Nota vazia</i></p>"
                    textFormat: Text.RichText
                    wrapMode: Text.Wrap
                    color: theme.palette.normal.baseText
                    font.pixelSize: units.gu(2.0)
                    onLinkActivated: {
                        if (link.indexOf("checkbox://") === 0) {
                            var lineIdx = parseInt(link.replace("checkbox://", ""), 10);
                            if (!isNaN(lineIdx)) {
                                noteEditPage.handleCheckboxToggle(lineIdx);
                            }
                        } else {
                            Qt.openUrlExternally(link);
                        }
                    }
                }
            }
        }

        // ==========================================
        // 2. MODO DE EDIÇÃO (COM SUPORTE AO TECLADO)
        // ==========================================
        Column {
            id: editContainer
            anchors.fill: parent
            anchors.margins: units.gu(1.5)
            visible: !noteEditPage.isPreviewMode
            spacing: units.gu(1)

            TextField {
                id: titleField
                width: parent.width
                placeholderText: "Título da Nota"
                font.bold: true
                font.pixelSize: units.gu(2.2)
                onTextChanged: {
                    if (noteEditPage.isLoaded) {
                        noteEditPage.hasUnsavedChanges = true;
                    }
                }
            }

            // Barra rápida de formatação Markdown, Recuo (Indentação) e Checklists
            Flickable {
                id: mdToolbar
                width: parent.width
                height: units.gu(4.2)
                contentWidth: mdToolbarRow.width
                contentHeight: height
                flickableDirection: Flickable.HorizontalFlick
                clip: true

                Row {
                    id: mdToolbarRow
                    height: parent.height
                    spacing: units.gu(0.6)

                    Button {
                        height: units.gu(3.8)
                        width: units.gu(5.2)
                        text: "⇤"
                        color: "#E8F0FE"
                        onClicked: noteEditPage.outdentCurrentLine()
                    }
                    Button {
                        height: units.gu(3.8)
                        width: units.gu(5.2)
                        text: "⇥"
                        color: "#E8F0FE"
                        onClicked: noteEditPage.indentCurrentLine()
                    }
                    Button {
                        height: units.gu(3.8)
                        width: units.gu(6.8)
                        text: "• Lista"
                        color: LomiriColors.porcelain
                        onClicked: noteEditPage.insertListItem("- ")
                    }
                    Button {
                        height: units.gu(3.8)
                        width: units.gu(8.2)
                        text: "☐ Tarefa"
                        color: LomiriColors.porcelain
                        onClicked: noteEditPage.insertListItem("- [ ] ")
                    }
                    Button {
                        height: units.gu(3.8)
                        width: units.gu(4.8)
                        text: "H1"
                        color: LomiriColors.porcelain
                        onClicked: noteEditPage.insertMarkdownSnippet("# ", "")
                    }
                    Button {
                        height: units.gu(3.8)
                        width: units.gu(4.8)
                        text: "H2"
                        color: LomiriColors.porcelain
                        onClicked: noteEditPage.insertMarkdownSnippet("## ", "")
                    }
                    Button {
                        height: units.gu(3.8)
                        width: units.gu(4.5)
                        text: "B"
                        color: LomiriColors.porcelain
                        onClicked: noteEditPage.insertMarkdownSnippet("**", "**")
                    }
                    Button {
                        height: units.gu(3.8)
                        width: units.gu(8.0)
                        text: "📁 Mover"
                        color: "#E8F0FE"
                        onClicked: PopupUtils.open(moveFolderDialog)
                    }
                    Button {
                        height: units.gu(3.8)
                        width: units.gu(7.6)
                        text: "🏷️ Tags"
                        color: "#FDEEE9"
                        onClicked: noteEditPage.openTagsManager()
                    }
                }
            }

            Rectangle {
                width: parent.width
                height: units.dp(1)
                color: theme.palette.normal.baseText
                opacity: 0.15
            }

            Flickable {
                id: bodyFlickable
                width: parent.width
                height: Math.max(units.gu(10), parent.height - titleField.height - mdToolbar.height - units.gu(3.5))
                contentWidth: width
                contentHeight: Math.max(height, bodyField.implicitHeight + units.gu(6))
                clip: true

                TextArea {
                    id: bodyField
                    width: parent.width
                    autoSize: true
                    maximumLineCount: 0
                    height: Math.max(bodyFlickable.height - units.gu(1), implicitHeight + units.gu(4))
                    placeholderText: "Escreva sua nota aqui em Markdown..."
                    wrapMode: TextEdit.Wrap
                    font.pixelSize: units.gu(1.9)
                    onTextChanged: {
                        if (!noteEditPage.isLoaded || noteEditPage.isAutoContinuingList) {
                            noteEditPage.previousBodyText = bodyField.text || "";
                            return;
                        }
                        noteEditPage.hasUnsavedChanges = true;
                        var oldText = noteEditPage.previousBodyText || "";
                        var newText = bodyField.text || "";
                        var oldNlCount = (oldText.match(/\n/g) || []).length;
                        var newNlCount = (newText.match(/\n/g) || []).length;
                        noteEditPage.previousBodyText = newText;

                        if (newNlCount === oldNlCount + 1 && newText.length >= oldText.length + 1 && (newText.length - oldText.length) <= 30) {
                            Qt.callLater(function() {
                                noteEditPage.handleBodyEnterContinuation();
                            });
                        }
                    }
                    onCursorRectangleChanged: {
                        noteEditPage.ensureCursorVisible();
                    }
                }
            }
        }
    }

    Component.onCompleted: {
        if (!isNewNote) {
            py.call('main.get_single_note', [noteEditPage.noteId], function(note) {
                if (note) {
                    noteEditPage.isLoaded = false;
                    titleField.text = note.title || "";
                    bodyField.text = note.body || "";
                    noteEditPage.previousBodyText = bodyField.text || "";
                    noteEditPage.folderId = note.parent_id || "";
                    noteEditPage.folderTitle = note.folder_title || "Sem Caderno";
                    noteEditPage.noteTagsList = note.tags || [];
                    noteEditPage.noteDirty = Number(note.dirty || 0);
                    noteEditPage.noteUpdatedDisplay = note.updated_display || "";
                    noteEditPage.renderedHtml = note.rendered_html || "";
                    noteEditPage.hasUnsavedChanges = false;
                    noteEditPage.isLoaded = true;
                }
            });
        } else {
            noteEditPage.previousBodyText = "";
            noteEditPage.isLoaded = true;
            noteEditPage.isPreviewMode = false;
            titleField.forceActiveFocus();
        }
    }
}
