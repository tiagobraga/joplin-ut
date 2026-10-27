import QtQuick 2.12
import Lomiri.Components 1.3

Page {
    id: settingsPage
    title: "Configurações"

    signal settingsSaved()

    property bool isTesting: false
    property bool isSyncing: false
    property string statusMessage: ""
    property bool statusSuccess: false

    header: PageHeader {
        title: "Configurações do Nextcloud"
    }

    function loadFormSettings() {
        try {
            py.call('main.get_app_settings', [], function(settings) {
                if (settings) {
                    serverUrlField.text = settings.server_url || "";
                    usernameField.text = settings.username || "";
                    passwordField.text = settings.password || "";
                    folderField.text = settings.joplin_dir || "Joplin";
                }
            });
        } catch (e) {
            console.error("Erro ao carregar configurações: " + e);
        }
    }

    Flickable {
        anchors.fill: parent
        anchors.margins: units.gu(2)
        contentHeight: settingsCol.height + units.gu(8)
        clip: true

        Column {
            id: settingsCol
            width: parent.width
            spacing: units.gu(2)

            Label {
                text: "Conexão com o Servidor Próprio"
                fontSize: "large"
                font.bold: true
                color: LomiriColors.slate
            }

            Label {
                text: "O Joplin UT conecta-se diretamente ao Nextcloud via WebDAV para sincronizar as notas em texto plano."
                wrapMode: Text.Wrap
                width: parent.width
                fontSize: "small"
                opacity: 0.7
            }

            // URL do Servidor
            Label { text: "URL do Nextcloud (ex: https://meunextcloud.com.br):"; font.bold: true }
            TextField {
                id: serverUrlField
                width: parent.width
                placeholderText: "https://meunextcloud.com.br"
                inputMethodHints: Qt.ImhUrlCharactersOnly
            }

            // Usuário
            Label { text: "Usuário:"; font.bold: true }
            TextField {
                id: usernameField
                width: parent.width
                placeholderText: "seu-usuario"
            }

            // Senha / Token
            Label { text: "Senha ou Token de App:"; font.bold: true }
            TextField {
                id: passwordField
                width: parent.width
                placeholderText: "••••••••••••"
                echoMode: TextInput.Password
            }

            // Diretório do Joplin
            Label { text: "Pasta no Nextcloud:"; font.bold: true }
            TextField {
                id: folderField
                width: parent.width
                text: "Joplin"
                placeholderText: "Joplin"
            }

            // Mensagem de status com indicador de progresso
            Rectangle {
                width: parent.width
                height: Math.max(statusRow.height + units.gu(2), units.gu(5))
                visible: settingsPage.statusMessage !== ""
                color: (settingsPage.isTesting || settingsPage.isSyncing) ? "#E8F0FE" : (settingsPage.statusSuccess ? "#D4EDDA" : "#F8D7DA")
                radius: units.gu(0.5)

                Row {
                    id: statusRow
                    anchors.centerIn: parent
                    spacing: units.gu(1)
                    width: parent.width - units.gu(2)

                    ActivityIndicator {
                        running: settingsPage.isTesting || settingsPage.isSyncing
                        visible: running
                    }

                    Label {
                        id: statusLabel
                        width: parent.width - (parent.children[0].visible ? units.gu(4) : 0)
                        text: settingsPage.statusMessage
                        wrapMode: Text.Wrap
                        color: (settingsPage.isTesting || settingsPage.isSyncing) ? "#1A73E8" : (settingsPage.statusSuccess ? "#155724" : "#721C24")
                        fontSize: "small"
                        font.bold: true
                    }
                }
            }

            // Botão de Testar Conexão
            Button {
                width: parent.width
                text: settingsPage.isTesting ? "Testando conexão..." : "Testar Conexão WebDAV"
                enabled: !settingsPage.isTesting && !settingsPage.isSyncing && serverUrlField.text.length > 0 && usernameField.text.length > 0
                onClicked: {
                    settingsPage.isTesting = true;
                    settingsPage.statusMessage = "Conectando ao servidor...";
                    try {
                        py.call('main.test_nextcloud_connection', [
                            serverUrlField.text,
                            usernameField.text,
                            passwordField.text,
                            folderField.text
                        ], function(result) {
                            settingsPage.isTesting = false;
                            if (result) {
                                settingsPage.statusSuccess = result.success;
                                settingsPage.statusMessage = result.message || (result.success ? "Conexão OK!" : "Falha na conexão.");
                            } else {
                                settingsPage.statusSuccess = false;
                                settingsPage.statusMessage = "Sem resposta do servidor.";
                            }
                        });
                    } catch (e) {
                        settingsPage.isTesting = false;
                        settingsPage.statusSuccess = false;
                        settingsPage.statusMessage = "Erro: " + e;
                    }
                }
            }

            // Botão Salvar e Sincronizar Agora
            Button {
                width: parent.width
                text: settingsPage.isSyncing ? "Sincronizando..." : "Salvar e Sincronizar Agora"
                color: "#1B5EBF"
                enabled: !settingsPage.isTesting && !settingsPage.isSyncing && serverUrlField.text.length > 0
                onClicked: {
                    settingsPage.isSyncing = true;
                    settingsPage.statusMessage = "Salvando credenciais e iniciando sincronização...";
                    try {
                        py.call('main.save_app_settings', [
                            serverUrlField.text,
                            usernameField.text,
                            passwordField.text,
                            folderField.text
                        ], function(saveResult) {
                            if (saveResult && saveResult.success) {
                                settingsPage.statusMessage = "Baixando cadernos e notas do Nextcloud...";
                                py.call('main.perform_sync', [false], function(syncResult) {
                                    settingsPage.isSyncing = false;
                                    if (syncResult && syncResult.success) {
                                        settingsPage.statusSuccess = true;
                                        settingsPage.statusMessage = syncResult.message;
                                        settingsPage.settingsSaved();
                                    } else {
                                        settingsPage.statusSuccess = false;
                                        settingsPage.statusMessage = syncResult.message || "Falha na sincronização.";
                                    }
                                });
                            } else {
                                settingsPage.isSyncing = false;
                                settingsPage.statusSuccess = false;
                                settingsPage.statusMessage = "Erro ao gravar configurações.";
                            }
                        });
                    } catch (e) {
                        settingsPage.isSyncing = false;
                        settingsPage.statusSuccess = false;
                        settingsPage.statusMessage = "Erro: " + e;
                    }
                }
            }

            // Botão Apenas Salvar
            Button {
                width: parent.width
                text: "Apenas Salvar Configurações"
                color: LomiriColors.orange
                enabled: !settingsPage.isTesting && !settingsPage.isSyncing
                onClicked: {
                    try {
                        py.call('main.save_app_settings', [
                            serverUrlField.text,
                            usernameField.text,
                            passwordField.text,
                            folderField.text
                        ], function(result) {
                            if (result && result.success) {
                                settingsPage.statusSuccess = true;
                                settingsPage.statusMessage = "Configurações salvas com sucesso!";
                                settingsPage.settingsSaved();
                            } else {
                                settingsPage.statusSuccess = false;
                                settingsPage.statusMessage = "Erro ao gravar configurações no dispositivo.";
                            }
                        });
                    } catch (e) {
                        settingsPage.statusSuccess = false;
                        settingsPage.statusMessage = "Erro ao salvar: " + e;
                    }
                }
            }
        }
    }

    Component.onCompleted: {
        loadFormSettings();
    }
}
