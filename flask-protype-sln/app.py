# app.py
import os
import requests
from flask import (Flask, render_template, request, jsonify, session,
                   redirect, url_for, flash)
from dotenv import load_dotenv
from requests.auth import HTTPBasicAuth
from functools import wraps # Para o decorator @login_required

# Carrega variáveis de ambiente do arquivo .env (para FLASK_SECRET_KEY)
load_dotenv()

app = Flask(__name__)
app.secret_key = os.getenv('FLASK_SECRET_KEY')

# Validação da chave secreta
if not app.secret_key:
    print("ERRO CRÍTICO: FLASK_SECRET_KEY não está definida no .env ou variáveis de ambiente!")
    print("A aplicação não funcionará corretamente sem uma chave secreta.")
    # Em produção, você pode querer sair aqui: import sys; sys.exit(1)


# --- Autenticação e Funções Auxiliares ---

def verify_jira_credentials(jira_instance, email, api_token):
    """Tenta autenticar na API do Jira para validar as credenciais."""
    if not all([jira_instance, email, api_token]):
        return False, "Instância, Email e API Token são obrigatórios."

    # Garante que a URL base esteja formatada corretamente
    base_url = jira_instance.strip()
    if not base_url.startswith(('http://', 'https://')):
        base_url = f"https://{base_url}"
    base_url = base_url.rstrip('/')

    # Endpoint de teste para verificar autenticação
    verify_url = f"{base_url}/rest/api/3/myself"
    auth = HTTPBasicAuth(email, api_token)
    headers = {"Accept": "application/json"}

    try:
        response = requests.get(verify_url, headers=headers, auth=auth, timeout=15)
        response.raise_for_status() # Lança erro para 4xx/5xx
        # Se chegou aqui, a autenticação funcionou
        user_data = response.json()
        print(f"Login verificado com sucesso para: {user_data.get('displayName', email)}")
        return True, base_url # Retorna True e a URL base formatada
    except requests.exceptions.HTTPError as http_err:
        status_code = http_err.response.status_code
        error_msg = f"Erro HTTP {status_code} ao verificar credenciais."
        if status_code == 401:
            error_msg = "Credenciais inválidas (Email ou API Token incorretos)."
        elif status_code == 403:
             error_msg = "Acesso proibido. Verifique permissões ou CAPTCHA no Jira."
        elif status_code == 404:
             error_msg = "Instância Jira não encontrada ou endpoint /myself indisponível."
        else:
            try: # Tenta pegar detalhes do erro da resposta
                 error_details = http_err.response.json()
                 error_msg += f" Detalhes: {error_details}"
            except ValueError:
                 error_msg += f" Resposta: {http_err.response.text[:100]}..." # Mostra início da resposta se não for JSON
        print(f"Falha na verificação: {error_msg}")
        return False, error_msg
    except requests.exceptions.ConnectionError:
        error_msg = f"Não foi possível conectar à instância: {base_url}. Verifique a URL e a rede."
        print(f"Falha na verificação: {error_msg}")
        return False, error_msg
    except requests.exceptions.Timeout:
        error_msg = "Timeout ao tentar conectar ao Jira para verificar credenciais."
        print(f"Falha na verificação: {error_msg}")
        return False, error_msg
    except Exception as e:
        error_msg = f"Erro inesperado durante a verificação: {e}"
        print(f"Falha na verificação: {error_msg}")
        return False, error_msg


def login_required(f):
    """Decorator para exigir login em certas rotas."""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'jira_email' not in session or 'jira_api_token' not in session or 'jira_instance_url' not in session:
            flash("Por favor, faça login para acessar esta página.", "warning")
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

# --- Rotas da Aplicação ---

@app.route('/login', methods=['GET', 'POST'])
def login():
    """Exibe o formulário de login e processa a tentativa de login."""
    if request.method == 'POST':
        jira_instance = request.form.get('jira_instance')
        email = request.form.get('email')
        api_token = request.form.get('api_token')

        is_valid, result_or_error = verify_jira_credentials(jira_instance, email, api_token)

        if is_valid:
            # Armazena credenciais e URL base validada na sessão
            session['jira_instance_url'] = result_or_error # Armazena a URL base validada
            session['jira_email'] = email
            session['jira_api_token'] = api_token
            session.permanent = True # Opcional: Torna a sessão mais duradoura
            flash("Login realizado com sucesso!", "success")
            return redirect(url_for('index'))
        else:
            flash(f"Falha no login: {result_or_error}", "danger")
            # Não redireciona, renderiza o login novamente com a mensagem de erro
            return render_template('login.html')

    # Método GET: apenas exibe o formulário de login
    # Se já estiver logado, redireciona para o index
    if 'jira_email' in session:
         return redirect(url_for('index'))
    return render_template('login.html')


@app.route('/logout')
def logout():
    """Limpa a sessão do usuário."""
    session.pop('jira_instance_url', None)
    session.pop('jira_email', None)
    session.pop('jira_api_token', None)
    flash("Você foi desconectado.", "info")
    return redirect(url_for('login'))


@app.route('/')
@login_required # Protege a rota principal
def index():
    """Serve a página HTML principal para criar issues (requer login)."""
    # Passa informações do usuário para o template (opcional)
    user_info = {
        'email': session.get('jira_email'),
        'instance': session.get('jira_instance_url')
    }
    return render_template('index.html', user_info=user_info)


# app.py
# ... (importações e código anterior) ...

@app.route('/search_issues', methods=['POST'])
@login_required # Protege a rota de busca
def search_jira_issues():
    """Recebe JQL via POST e busca issues usando a API v2 do Jira."""

    jira_instance_url = session['jira_instance_url']
    email = session['jira_email']
    api_token = session['jira_api_token']

    try:
        data = request.get_json()
        jql_query = data.get('jql')

        if not jql_query:
            return jsonify({"error": "Consulta JQL não fornecida."}), 400

        # API v2 endpoint for search
        search_url = f"{jira_instance_url}/rest/api/2/search"

        # Parâmetros da requisição GET para a API do Jira
        params = {
            'jql': jql_query,
            # Campos que queremos retornar (otimização)
            'fields': 'key,summary,status,assignee,issuetype',
            'maxResults': 100 # Limita o número de resultados (ajuste conforme necessário)
            # 'startAt': 0 # Para paginação futura
        }

        headers = {"Accept": "application/json"}
        auth = HTTPBasicAuth(email, api_token)

        # Faz a requisição GET para a API do Jira
        response = requests.get(
            search_url,
            headers=headers,
            params=params, # Parâmetros vão na URL para GET
            auth=auth,
            timeout=30
        )

        # Verifica se o token ainda é válido (pode ter sido revogado)
        if response.status_code == 401:
             session.clear()
             return jsonify({"error": "Sua sessão expirou ou o API Token tornou-se inválido. Faça login novamente.", "redirect": url_for('login')}), 401

        # Verifica outros erros HTTP (como 400 Bad Request para JQL inválida)
        response.raise_for_status() # Lança exceção para 4xx/5xx (exceto 401 tratado acima)

        # Processa a resposta de sucesso
        jira_response = response.json()
        issues_raw = jira_response.get('issues', [])

        # Simplifica os dados antes de enviar para o frontend
        simplified_issues = []
        for issue in issues_raw:
            fields = issue.get('fields', {})
            assignee_info = fields.get('assignee')
            status_info = fields.get('status')
            issuetype_info = fields.get('issuetype')

            simplified_issues.append({
                'key': issue.get('key'),
                'url': f"{jira_instance_url}/browse/{issue.get('key')}",
                'summary': fields.get('summary'),
                'status': status_info.get('name') if status_info else 'N/A',
                'assignee': assignee_info.get('displayName') if assignee_info else None, # Pode ser None
                'issuetype': issuetype_info.get('name') if issuetype_info else 'N/A'
            })

        return jsonify({"issues": simplified_issues}), 200

    except requests.exceptions.HTTPError as http_err:
        status_code = http_err.response.status_code
        error_message = f"Erro na busca ({status_code})"
        details = ""
        try:
            # Tenta pegar a mensagem de erro específica do Jira (útil para JQL inválido)
            error_details = http_err.response.json()
            jira_errors = error_details.get('errorMessages', [])
            if jira_errors:
                 error_message += f": {', '.join(jira_errors)}"
                 details = ', '.join(jira_errors) # Guarda detalhes para possível uso no JS
            # Adiciona erros de campos específicos se houver (raro em busca, mas possível)
            field_errors = error_details.get('errors', {})
            if field_errors:
                 error_message += f" Errors: {field_errors}"

        except ValueError: # Se a resposta de erro não for JSON
            error_message += f": {http_err.response.text[:200]}..." # Limita tamanho

        print(f"Erro HTTP ao buscar issues: {error_message}")
        # Retorna detalhes no erro para o JS poder checar se é JQL inválido
        return jsonify({"error": error_message, "details": details}), status_code

    except requests.exceptions.RequestException as req_err:
        print(f"Erro de Rede/Requisição ao buscar issues: {req_err}")
        return jsonify({"error": f"Erro de comunicação ao buscar issues: {req_err}"}), 500
    except Exception as e:
        print(f"Erro inesperado no servidor ao buscar issues: {e}")
        # Adiciona traceback para debug se necessário: import traceback; traceback.print_exc()
        return jsonify({"error": f"Ocorreu um erro interno no servidor: {e}"}), 500

# ... (restante do app.py, if __name__ == '__main__': etc.)

@app.route('/create_issue', methods=['POST'])
@login_required # Protege a API de criação de issue
def create_jira_issue():
    """Recebe dados do formulário e cria a issue no Jira usando credenciais da sessão."""

    # Recupera credenciais da sessão (já validadas pelo @login_required)
    jira_instance_url = session['jira_instance_url']
    email = session['jira_email']
    api_token = session['jira_api_token']

    try:
        data = request.get_json()
        project_key = data.get('projectKey')
        issue_type_id = data.get('issueTypeId')
        summary = data.get('summary')
        description_text = data.get('description', '')

        if not all([project_key, issue_type_id, summary]):
            return jsonify({"error": "Campos obrigatórios (Chave do Projeto, ID do Tipo, Resumo) não fornecidos."}), 400

        api_url = f"{jira_instance_url}/rest/api/3/issue"
        payload = {
            "fields": {
                "project": {"key": project_key.upper()},
                "issuetype": {"id": issue_type_id},
                "summary": summary,
                "description": {
                    "type": "doc", "version": 1,
                    "content": [{"type": "paragraph", "content": [{"type": "text", "text": description_text or " "}]}]
                }
            }
        }
        headers = {"Accept": "application/json", "Content-Type": "application/json"}
        auth = HTTPBasicAuth(email, api_token)

        response = requests.post(api_url, json=payload, headers=headers, auth=auth, timeout=30)

        # Verifica se o token ainda é válido (pode ter sido revogado desde o login)
        if response.status_code == 401:
             # Limpa a sessão e pede novo login
             session.clear()
             return jsonify({"error": "Sua sessão expirou ou o API Token tornou-se inválido. Faça login novamente.", "redirect": url_for('login')}), 401

        response.raise_for_status() # Lança exceção para outros erros (4xx, 5xx)

        jira_response = response.json()
        issue_key = jira_response.get('key')
        issue_url = f"{jira_instance_url}/browse/{issue_key}"

        return jsonify({
            "message": f"Issue criada com sucesso: {issue_key}",
            "issueKey": issue_key,
            "issueUrl": issue_url
        }), 201

    except requests.exceptions.HTTPError as http_err:
        status_code = http_err.response.status_code
        try:
            error_details = http_err.response.json()
            error_message = f"Erro do Jira ({status_code}): {error_details.get('errorMessages', [])} {error_details.get('errors', {})}"
        except ValueError:
            error_message = f"Erro HTTP ({status_code}): {http_err.response.text}"
        print(f"Erro HTTP ao criar issue: {error_message}")
        return jsonify({"error": error_message}), status_code
    except requests.exceptions.RequestException as req_err:
        print(f"Erro na Requisição ao criar issue: {req_err}")
        return jsonify({"error": f"Ocorreu um erro de comunicação ao tentar criar a issue: {req_err}"}), 500
    except Exception as e:
        print(f"Erro inesperado no servidor ao criar issue: {e}")
        return jsonify({"error": f"Ocorreu um erro interno no servidor: {e}"}), 500


if __name__ == '__main__':
    # Use uma porta diferente se necessário
    # debug=True é ótimo para desenvolvimento, mas NUNCA use em produção com esta chave secreta hardcoded!
    # Em produção, use Gunicorn/Waitress + Nginx/Apache com HTTPS.
    app.run(host='0.0.0.0', port=5001, debug=True)