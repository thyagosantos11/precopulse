# Preço Pulse

Monitor de preços com interface web, backend Flask e suporte a múltiplos produtos.

## Estrutura

```
price_tracker/
├── app.py              # Backend Flask
├── requirements.txt    # Dependências Python
├── templates/
│   └── index.html      # Interface web
├── tracker.db       # Banco de dados SQLite
```

## Instalação

```bash
# 1. Instalar dependências
pip install -r requirements.txt

# 2. Rodar o servidor
python app.py
```

Acesse: http://localhost:5000

## Configuração

1. Abra a interface em `http://localhost:5000`
2. Vá em **Configurações** e preencha:
   - E-mail de envio (Gmail)
   - E-mail de destino
   - Senha de app Gmail (gere em: https://myaccount.google.com/apppasswords)
   - Intervalo de verificação (1–24h)
3. Vá em **Produtos** → **Adicionar produto**
4. Cole a URL do produto e defina o limite de preço
5. Clique em **↻** para verificar agora, ou aguarde a verificação automática

## Como gerar a senha de app do Gmail

1. Acesse https://myaccount.google.com/security
2. Ative a verificação em duas etapas (se ainda não tiver)
3. Acesse https://myaccount.google.com/apppasswords
4. Crie uma senha de app para "Mail"
5. Use a senha gerada (formato: xxxx xxxx xxxx xxxx)

## API

| Método | Rota | Descrição |
|--------|------|-----------|
| GET | /api/products | Lista produtos |
| POST | /api/products | Adiciona produto |
| PUT | /api/products/:id | Edita produto |
| DELETE | /api/products/:id | Remove produto |
| POST | /api/products/:id/check | Verifica preço agora |
| GET | /api/settings | Retorna configurações |
| POST | /api/settings | Salva configurações |
| GET | /api/logs | Últimas 50 entradas do log |

## Observações

- O scraper foi feito para `seiziguitars.com.br`. Para outros sites, pode ser necessário ajustar o seletor CSS em `scrape_price()` no `app.py`.
- A verificação automática roda em background enquanto o servidor estiver ativo.
- Os dados são salvos em arquivos `.json` localmente.
