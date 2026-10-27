import QtQuick 2.12
import Lomiri.Components 1.3
import Lomiri.Components.Popups 1.3
import io.thp.pyotherside 1.5

import "components"
import "pages"

MainView {
    id: root
    objectName: "mainView"
    applicationName: "joplin-ut.braga"

    width: units.gu(45)
    height: units.gu(80)

    // Tema padrão Lomiri
    theme.name: "Lomiri.Components.Themes.Ambiance"

    property bool isDrawerOpen: false
    property bool isReady: false
    property var allFolders: []
    property var allTags: []

    onIsDrawerOpenChanged: {
        if (isDrawerOpen && isReady) {
            refreshSyncStatus();
        }
    }

    // Ponte com o Python
    Python {
        id: py

        Component.onCompleted: {
            var rawUrl = Qt.resolvedUrl('../src').toString();
            var srcPath = rawUrl.replace(/^file:\/\//, '');
            console.log("[Joplin UT] Adding Python sys.path:", srcPath);
            addImportPath(srcPath);
            importModule('main', function() {
                console.log("[Joplin UT] Python module 'main' imported successfully.");
                py.call('main.init_app', [], function(res) {
                    console.log("[Joplin UT] Backend Python inicializado com sucesso:", res);
                    root.isReady = true;
                    refreshFolders();
                });
            });
        }

        onError: {
            console.error("[Joplin UT Python Error]: " + traceback);
        }
    }

    function refreshSyncStatus() {
        if (!root.isReady) return;
        py.call('main.get_sync_status', [], function(status) {
            if (status) {
                drawerComponent.lastSyncText = String(status.last_sync || "Nunca");
                drawerComponent.pendingCount = Number(status.pending_count || 0);
            }
        });
    }

    function refreshFolders() {
        if (!root.isReady) return;
        py.call('main.get_folders_list', [], function(folders) {
            root.allFolders = folders || [];
            drawerComponent.foldersModel = root.allFolders;
        });
        py.call('main.get_tags_list', [], function(tags) {
            root.allTags = tags || [];
            drawerComponent.tagsModel = root.allTags;
        });
        refreshSyncStatus();
    }

    Timer {
        id: clearDrawerSyncMsgTimer
        interval: 6000
        repeat: false
        onTriggered: {
            drawerComponent.syncMessageText = "";
        }
    }

    function runDrawerSync(forceFull) {
        if (!root.isReady || drawerComponent.isSyncing) return;
        drawerComponent.isSyncing = true;
        drawerComponent.syncMessageText = forceFull
            ? "Verificando todos os arquivos no Nextcloud..."
            : "Sincronizando alterações com o Nextcloud...";

        py.call('main.perform_sync', [Boolean(forceFull)], function(res) {
            drawerComponent.isSyncing = false;
            if (res && res.success) {
                if (res.last_sync) {
                    drawerComponent.lastSyncText = String(res.last_sync);
                }
                drawerComponent.syncMessageText = String(res.message || "Sincronização concluída!");
                refreshFolders();
                if (pageStack.currentPage && pageStack.currentPage.loadNotes) {
                    pageStack.currentPage.loadNotes();
                }
            } else {
                drawerComponent.syncMessageText = (res && res.message) ? String(res.message) : "Erro de sincronização.";
                refreshSyncStatus();
            }
            clearDrawerSyncMsgTimer.restart();
        });
    }

    function getFolderTitleById(fId) {
        if (!fId || String(fId).indexOf("tag:") === 0) return "Sem Caderno";
        for (var i = 0; i < root.allFolders.length; i++) {
            if (root.allFolders[i] && String(root.allFolders[i].id) === String(fId)) {
                return String(root.allFolders[i].title || "Sem Caderno");
            }
        }
        return "Sem Caderno";
    }

    // Pilha de páginas principal
    PageStack {
        id: pageStack
        anchors.fill: parent

        Component.onCompleted: {
            pageStack.push(notesListPageComponent);
        }
    }

    // Componente da Lista de Notas
    Component {
        id: notesListPageComponent
        NotesListPage {
            id: listPage
            onToggleDrawer: {
                root.isDrawerOpen = !root.isDrawerOpen;
            }
            onOpenSettings: {
                pageStack.push(settingsPageComponent);
            }
            onOpenNote: {
                var effectiveFolderId = folderId || listPage.currentFolderId || "";
                if (String(effectiveFolderId).indexOf("tag:") === 0) {
                    effectiveFolderId = "";
                }
                pageStack.push(noteEditPageComponent, {
                    noteId: noteId,
                    folderId: effectiveFolderId,
                    folderTitle: root.getFolderTitleById(effectiveFolderId),
                    foldersList: root.allFolders,
                    allTagsList: root.allTags
                });
            }
        }
    }

    // Componente do Editor de Notas
    Component {
        id: noteEditPageComponent
        NoteEditPage {
            foldersList: root.allFolders
            allTagsList: root.allTags
            onNoteSaved: {
                refreshFolders();
                if (pageStack.currentPage && pageStack.currentPage.loadNotes) {
                    pageStack.currentPage.loadNotes();
                }
            }
            onNoteDeleted: {
                refreshFolders();
                if (pageStack.currentPage && pageStack.currentPage.loadNotes) {
                    pageStack.currentPage.loadNotes();
                }
            }
            onTagsUpdated: {
                refreshFolders();
                if (pageStack.currentPage && pageStack.currentPage.loadNotes) {
                    pageStack.currentPage.loadNotes();
                }
            }
        }
    }

    // Componente de Configurações
    Component {
        id: settingsPageComponent
        SettingsPage {
            onSettingsSaved: {
                refreshFolders();
                // Fecha a tela de configurações voltando para a lista
                while (pageStack.depth > 1) {
                    pageStack.pop();
                }
                if (pageStack.currentPage && pageStack.currentPage.loadNotes) {
                    pageStack.currentPage.loadNotes();
                }
            }
        }
    }

    // Backdrop escuro para fechar a gaveta ao clicar fora
    Rectangle {
        id: drawerBackdrop
        anchors.fill: parent
        color: "#000000"
        opacity: root.isDrawerOpen ? 0.45 : 0.0
        visible: opacity > 0.0
        z: 99

        Behavior on opacity {
            NumberAnimation { duration: 250; easing.type: Easing.InOutQuad }
        }

        MouseArea {
            anchors.fill: parent
            enabled: root.isDrawerOpen
            onClicked: root.isDrawerOpen = false;
        }
    }

    // Gaveta de Cadernos Lateral (Drawer)
    NotebookDrawer {
        id: drawerComponent
        z: 100
        x: root.isDrawerOpen ? 0 : -width

        Behavior on x {
            NumberAnimation { duration: 250; easing.type: Easing.OutQuad }
        }

        onFolderSelected: {
            root.isDrawerOpen = false;
            // Se estiver em outra página, volta para a lista principal
            while (pageStack.depth > 1) {
                pageStack.pop();
            }
            if (pageStack.currentPage) {
                pageStack.currentPage.currentFolderId = folderId;
                pageStack.currentPage.currentFolderTitle = folderTitle;
                pageStack.currentPage.loadNotes();
            }
        }

        onNewFolderRequested: {
            root.isDrawerOpen = false;
            var activeId = drawerComponent.selectedFolderId || "";
            if (String(activeId).indexOf("tag:") === 0) {
                activeId = "";
            }
            var activeTitle = "";
            if (activeId) {
                for (var i = 0; i < root.allFolders.length; i++) {
                    if (root.allFolders[i] && String(root.allFolders[i].id) === activeId) {
                        activeTitle = root.allFolders[i].title || "";
                        break;
                    }
                }
            }
            PopupUtils.open(newFolderDialog, root, {
                parentFolderId: activeId,
                parentFolderTitle: activeTitle
            });
        }

        onFolderOptionsRequested: {
            root.isDrawerOpen = false;
            PopupUtils.open(folderOptionsDialog, root, {
                targetFolderId: folderId,
                targetFolderTitle: folderTitle
            });
        }

        onNewTagRequested: {
            root.isDrawerOpen = false;
            PopupUtils.open(newTagDialog, root);
        }

        onTagOptionsRequested: {
            root.isDrawerOpen = false;
            PopupUtils.open(tagOptionsDialog, root, {
                targetTagId: tagId,
                targetTagTitle: tagTitle
            });
        }

        onSyncRequested: {
            root.runDrawerSync(forceFull);
        }
    }

    // Diálogo para criação de novo caderno (raiz ou subcaderno)
    Component {
        id: newFolderDialog
        Dialog {
            id: folderDlg
            property string parentFolderId: ""
            property string parentFolderTitle: ""
            property bool createAsSubfolder: parentFolderId !== ""

            title: createAsSubfolder ? "Novo Subcaderno" : "Novo Caderno"
            text: createAsSubfolder
                  ? ("Criar dentro de \"" + parentFolderTitle + "\":")
                  : "Digite o nome para o novo caderno principal:"

            TextField {
                id: newFolderField
                placeholderText: "Nome do caderno"
            }

            Button {
                visible: folderDlg.parentFolderId !== ""
                text: folderDlg.createAsSubfolder ? "Criar na Raiz (Principal)" : ("Criar dentro de " + folderDlg.parentFolderTitle)
                color: LomiriColors.porcelain
                onClicked: {
                    folderDlg.createAsSubfolder = !folderDlg.createAsSubfolder;
                }
            }

            Button {
                text: "Criar"
                color: LomiriColors.orange
                enabled: newFolderField.text.trim().length > 0
                onClicked: {
                    var title = newFolderField.text.trim();
                    var pId = folderDlg.createAsSubfolder ? (folderDlg.parentFolderId || "") : "";
                    PopupUtils.close(folderDlg);
                    py.call('main.create_folder', [title, pId], function(res) {
                        if (res && res.success) {
                            refreshFolders();
                        }
                    });
                }
            }

            Button {
                text: "Cancelar"
                onClicked: PopupUtils.close(folderDlg);
            }
        }
    }

    // Diálogo de opções do caderno (toque longo na gaveta: Renomear, Criar Subcaderno ou Excluir)
    Component {
        id: folderOptionsDialog
        Dialog {
            id: folderOptDlg
            property string targetFolderId: ""
            property string targetFolderTitle: ""

            title: "Caderno: " + targetFolderTitle
            text: "Renomear, criar subcaderno ou excluir:"

            TextField {
                id: renameFolderField
                text: folderOptDlg.targetFolderTitle
                placeholderText: "Novo nome do caderno"
            }

            Button {
                text: "Salvar Novo Nome"
                color: "#1B5EBF"
                enabled: renameFolderField.text.trim().length > 0 && renameFolderField.text.trim() !== folderOptDlg.targetFolderTitle
                onClicked: {
                    var newName = renameFolderField.text.trim();
                    var fId = folderOptDlg.targetFolderId || "";
                    PopupUtils.close(folderOptDlg);
                    py.call('main.rename_folder', [fId, newName], function(res) {
                        if (res && res.success) {
                            refreshFolders();
                            if (pageStack.currentPage && pageStack.currentPage.currentFolderId === fId) {
                                pageStack.currentPage.currentFolderTitle = newName;
                            }
                        }
                    });
                }
            }

            Button {
                text: "+ Criar Subcaderno Aqui"
                color: LomiriColors.orange
                onClicked: {
                    var fId = folderOptDlg.targetFolderId || "";
                    var fTitle = folderOptDlg.targetFolderTitle || "";
                    PopupUtils.close(folderOptDlg);
                    PopupUtils.open(newFolderDialog, root, {
                        parentFolderId: fId,
                        parentFolderTitle: fTitle
                    });
                }
            }

            Button {
                text: "Excluir Caderno"
                color: LomiriColors.red
                onClicked: {
                    var fId = folderOptDlg.targetFolderId || "";
                    PopupUtils.close(folderOptDlg);
                    py.call('main.delete_folder', [fId], function(res) {
                        if (res && res.success) {
                            refreshFolders();
                            if (pageStack.currentPage && pageStack.currentPage.currentFolderId === fId) {
                                pageStack.currentPage.currentFolderId = "";
                                pageStack.currentPage.currentFolderTitle = "Todas as Notas";
                                pageStack.currentPage.loadNotes();
                            }
                        }
                    });
                }
            }

            Button {
                text: "Cancelar"
                onClicked: PopupUtils.close(folderOptDlg);
            }
        }
    }

    // Diálogo para criação de nova etiqueta (tag)
    Component {
        id: newTagDialog
        Dialog {
            id: tagDlg
            title: "Nova Etiqueta (Tag)"
            text: "Digite o nome da nova tag:"

            TextField {
                id: newTagField
                placeholderText: "Ex: urgente, ideias, projeto..."
            }

            Button {
                text: "Criar Tag"
                color: "#1B5EBF"
                enabled: newTagField.text.trim().length > 0
                onClicked: {
                    var title = newTagField.text.trim();
                    PopupUtils.close(tagDlg);
                    py.call('main.create_tag', [title, ""], function(res) {
                        if (res && res.success) {
                            refreshFolders();
                        }
                    });
                }
            }

            Button {
                text: "Cancelar"
                onClicked: PopupUtils.close(tagDlg);
            }
        }
    }

    // Diálogo de opções da tag (toque longo na gaveta: Renomear ou Excluir)
    Component {
        id: tagOptionsDialog
        Dialog {
            id: tagOptDlg
            property string targetTagId: ""
            property string targetTagTitle: ""

            title: "Tag: #" + targetTagTitle
            text: "Renomear ou excluir esta etiqueta:"

            TextField {
                id: renameTagField
                text: tagOptDlg.targetTagTitle
                placeholderText: "Novo nome da tag"
            }

            Button {
                text: "Salvar Novo Nome"
                color: "#1B5EBF"
                enabled: renameTagField.text.trim().length > 0 && renameTagField.text.trim() !== tagOptDlg.targetTagTitle
                onClicked: {
                    var newName = renameTagField.text.trim();
                    var tId = tagOptDlg.targetTagId || "";
                    PopupUtils.close(tagOptDlg);
                    py.call('main.rename_tag', [tId, newName], function(res) {
                        if (res && res.success) {
                            refreshFolders();
                            if (pageStack.currentPage && pageStack.currentPage.currentFolderId === ("tag:" + tId)) {
                                pageStack.currentPage.currentFolderTitle = "# " + newName;
                            }
                        }
                    });
                }
            }

            Button {
                text: "Excluir Tag"
                color: LomiriColors.red
                onClicked: {
                    var tId = tagOptDlg.targetTagId || "";
                    PopupUtils.close(tagOptDlg);
                    py.call('main.delete_tag', [tId], function(res) {
                        if (res && res.success) {
                            refreshFolders();
                            if (pageStack.currentPage && pageStack.currentPage.currentFolderId === ("tag:" + tId)) {
                                pageStack.currentPage.currentFolderId = "";
                                pageStack.currentPage.currentFolderTitle = "Todas as Notas";
                                pageStack.currentPage.loadNotes();
                            }
                        }
                    });
                }
            }

            Button {
                text: "Cancelar"
                onClicked: PopupUtils.close(tagOptDlg);
            }
        }
    }
}
