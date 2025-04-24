// static/script.js

// Certifique-se de que o DOM está pronto (opcional, mas boa prática)
// Removido o DOMContentLoaded para simplificar, pois o script é carregado no fim do body.
// document.addEventListener('DOMContentLoaded', () => {

    // --- Seletores de Elementos ---
    const createForm = document.getElementById('jira-form');
    const createStatusDiv = document.getElementById('status');
    const createSubmitButton = document.getElementById('submit-button');

    const searchForm = document.getElementById('search-form');
    const searchStatusDiv = document.getElementById('search-status');
    const searchButton = document.getElementById('search-button');
    const searchResultsDiv = document.getElementById('search-results');
    const searchResultsTable = document.getElementById('search-results-table');
    // Verifica se a tabela existe antes de tentar selecionar o tbody
    const searchResultsTbody = searchResultsTable ? searchResultsTable.querySelector('tbody') : null;

    // --- Lógica para Criar Issue ---
    if (createForm) { // Verifica se o formulário existe na página
        createForm.addEventListener('submit', function(event) {
            event.preventDefault();
            showStatus(createStatusDiv, 'Enviando criação...', 'info');
            if(createSubmitButton) createSubmitButton.disabled = true;

            const createData = {
                projectKey: document.getElementById('project-key').value.trim(),
                issueTypeId: document.getElementById('issue-type-id').value.trim(),
                summary: document.getElementById('summary').value.trim(),
                description: document.getElementById('description').value.trim()
            };

            // Usa a URL passada do HTML através da variável global 'config'
            fetch(config.createIssueUrl, {
                method: 'POST',
                headers: {'Content-Type': 'application/json', 'Accept': 'application/json'},
                body: JSON.stringify(createData)
            })
            .then(handleFetchResponse)
            .then(result => {
                if (result.ok) {
                    showStatus(createStatusDiv, `Sucesso! ${result.data.message} <a href="${result.data.issueUrl}" target="_blank">Ver Issue</a>`, 'success');
                    createForm.reset();
                } else {
                    showStatus(createStatusDiv, `Erro ${result.status}: ${result.data.error || 'Erro desconhecido.'}`, 'error');
                }
            })
            .catch(error => {
                console.error('Erro ao criar issue:', error);
                showStatus(createStatusDiv, `Erro: ${error.message}`, 'error');
            })
            .finally(() => {
                if(createSubmitButton) createSubmitButton.disabled = false;
            });
        });
    } // fim if(createForm)

    // --- Lógica para Buscar Issues ---
    if (searchForm && searchResultsTbody) { // Verifica se os elementos de busca existem
        searchForm.addEventListener('submit', function(event) {
            event.preventDefault();
            showStatus(searchStatusDiv, 'Buscando issues...', 'info');
            if(searchButton) searchButton.disabled = true;
            searchResultsTbody.innerHTML = ''; // Limpa resultados anteriores
            if(searchResultsTable) searchResultsTable.style.display = 'none'; // Esconde tabela

            const jqlQuery = document.getElementById('jql-query').value.trim();

            if (!jqlQuery) {
                showStatus(searchStatusDiv, 'Por favor, insira uma consulta JQL.', 'error');
                 if(searchButton) searchButton.disabled = false;
                return;
            }

            // Usa a URL passada do HTML através da variável global 'config'
            fetch(config.searchIssuesUrl, {
                method: 'POST',
                headers: {'Content-Type': 'application/json', 'Accept': 'application/json'},
                body: JSON.stringify({ jql: jqlQuery })
            })
            .then(handleFetchResponse)
            .then(result => {
                if (result.ok) {
                    const issues = result.data.issues;
                    if (issues && issues.length > 0) {
                        showStatus(searchStatusDiv, `Encontradas ${issues.length} issues.`, 'success');
                        displaySearchResults(issues);
                    } else {
                        showStatus(searchStatusDiv, 'Nenhuma issue encontrada para esta consulta.', 'info');
                    }
                } else {
                     let errMsg = `Erro ${result.status}: ${result.data.error || 'Erro desconhecido.'}`;
                     if (result.data.details && result.data.details.includes("Error in the JQL Query")) {
                          errMsg += " Verifique a sintaxe da sua consulta JQL.";
                     }
                    showStatus(searchStatusDiv, errMsg, 'error');
                }
            })
            .catch(error => {
                console.error('Erro ao buscar issues:', error);
                showStatus(searchStatusDiv, `Erro: ${error.message}`, 'error');
            })
            .finally(() => {
                 if(searchButton) searchButton.disabled = false;
            });
        });
    } // fim if(searchForm)


    // --- Funções Auxiliares ---

    function displaySearchResults(issues) {
        if (!searchResultsTbody || !searchResultsTable) return; // Garante que os elementos existem
        searchResultsTbody.innerHTML = '';
        issues.forEach(issue => {
            const row = searchResultsTbody.insertRow();
            const cellKey = row.insertCell();
            const link = document.createElement('a');
            link.href = issue.url;
            link.textContent = issue.key;
            link.target = '_blank';
            cellKey.appendChild(link);
            row.insertCell().textContent = issue.summary || '';
            row.insertCell().textContent = issue.issuetype || '';
            row.insertCell().textContent = issue.status || '';
            row.insertCell().textContent = issue.assignee || 'Não atribuído';
        });
        searchResultsTable.style.display = 'table';
    }

    function handleFetchResponse(response) {
         if (response.status === 401) {
             return response.json().then(data => {
                 if (data && data.redirect) {
                      // Usa a URL de login passada do HTML via 'config'
                      window.location.href = data.redirect || config.loginUrl;
                 } else {
                      window.location.href = config.loginUrl; // Fallback
                 }
                 throw new Error(data.error || "Sessão inválida ou token revogado. Faça login novamente.");
             }).catch(e => {
                  console.error("Erro 401, redirecionando para login.", e);
                  window.location.href = config.loginUrl; // Fallback mais robusto
                  throw new Error("Sessão inválida. Redirecionando para login.");
             });
         }
         return response.json().then(data => ({
            ok: response.ok,
            status: response.status,
            data: data
         })).catch(parseError => {
            console.error("Falha ao parsear resposta JSON:", response.status, parseError);
             return {
                  ok: false,
                  status: response.status,
                  data: { error: `Erro ${response.status}: Resposta inválida do servidor.` }
             };
         });
    }

    function showStatus(element, message, type) {
        if (!element) return; // Verifica se o elemento de status existe
        element.innerHTML = message;
        element.className = type;
    }

// }); // Fecha o DOMContentLoaded se estiver usando