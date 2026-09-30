# LinkedIn Agent

Agente que gera posts sobre a área de dados com o **Claude Code** e publica no LinkedIn pela **API oficial**, agendado pelo Agendador de Tarefas do Windows.

Nada é publicado sem aprovação: o Claude gera rascunhos, você revisa, e só o que estiver na pasta de aprovados vai para o ar.

## Como funciona

```
generate.py ──> queue/pending/ ──(você revisa e move)──> queue/approved/ ──> publish.py ──> LinkedIn
     ▲                                                                           │
     └──────────────────────────── history.md <──────────────────────────────────┘
```

1. **`generate.py`** monta um contexto com `guidelines.md`, o histórico de posts publicados e os posts já na fila, e chama o Claude Code em modo headless (`claude -p`). Cada rascunho é salvo em `queue/pending/`.
2. **Você** lê os rascunhos, edita se quiser, e move os bons para `queue/approved/`.
3. **`publish.py`** pega o post aprovado mais antigo, publica via API do LinkedIn, move o arquivo para `queue/posted/` e registra em `history.md`. Se não houver post aprovado, ele simplesmente não faz nada naquele horário.
4. O histórico realimenta o gerador, evitando temas e ângulos repetidos.

## Estrutura

```
linkedin-agent/
├── auth.py               # Login OAuth no LinkedIn (salva token em config.json)
├── generate.py           # Gera rascunhos com o Claude Code
├── publish.py            # Publica o próximo post aprovado
├── guidelines.md         # Quem você é, público, temas, estilo e regras
├── config.example.json   # Modelo de configuração
├── config.json           # Suas chaves e token (NÃO versionar)
├── run_generate.bat      # Usado pelo Agendador de Tarefas
├── run_publish.bat       # Usado pelo Agendador de Tarefas
├── history.md            # Criado automaticamente
├── log.txt               # Criado automaticamente
└── queue/
    ├── pending/          # Rascunhos aguardando revisão
    ├── approved/         # Aprovados, na fila de publicação
    └── posted/           # Já publicados
```

## Pré-requisitos

- Windows com Python 3 (`python --version`)
- Biblioteca `requests`: `pip install requests`
- Claude Code instalado e autenticado (`claude --version` deve funcionar no cmd)
- Uma Página do LinkedIn (obrigatória para criar o app de desenvolvedor)

## Configuração do LinkedIn

1. **Página:** se ainda não tiver, crie uma em LinkedIn → "Para empresas" → "Criar Página".
2. **App:** em https://developer.linkedin.com, clique em "Create app", associe à Página e crie. Na aba **Settings**, clique em **Verify** e aprove o link como admin da Página.
3. **Produtos:** na aba **Products**, solicite:
   - *Share on LinkedIn*
   - *Sign In with LinkedIn using OpenID Connect*
4. **Auth:** na aba **Auth**:
   - Copie o **Client ID** e o **Primary Client Secret**
   - Adicione a redirect URL `http://localhost:8000/callback`
   - Confira se os escopos `openid`, `profile` e `w_member_social` aparecem

## Instalação

```bat
cd C:\linkedin-agent
pip install requests
copy config.example.json config.json
```

Edite `config.json` com seu Client ID e Secret. Depois faça o login:

```bat
python auth.py
```

O navegador abre, você autoriza o app e o token é salvo em `config.json`.

Por fim, preencha o `guidelines.md`, principalmente a seção **"Who I am"** com seu cargo, stack e experiência reais. Quanto mais específico, menos genéricos ficam os posts.

## Uso

```bat
:: Gerar rascunhos (padrão: 1)
python generate.py 5

:: Ver o que seria publicado, sem publicar
python publish.py --dry-run

:: Publicar o próximo post aprovado
python publish.py
```

## Agendamento

```bat
schtasks /create /tn "LinkedIn Publish AM" /tr "C:\linkedin-agent\run_publish.bat" /sc daily /st 09:00
schtasks /create /tn "LinkedIn Publish PM" /tr "C:\linkedin-agent\run_publish.bat" /sc daily /st 17:00
schtasks /create /tn "LinkedIn Generate" /tr "C:\linkedin-agent\run_generate.bat" /sc weekly /d SUN /st 18:00
```

Isso gera 10 rascunhos todo domingo e publica às 9h e às 17h. Por padrão, as tarefas só rodam com o PC ligado e seu usuário logado no Windows.

Para remover uma tarefa: `schtasks /delete /tn "LinkedIn Publish AM"`

### Rotina semanal

1. Domingo à noite, abra `queue/pending/`.
2. Leia os rascunhos, ajuste o texto se precisar e mova os bons para `queue/approved/`.
3. Apague os que não prestaram.

Com 10 aprovados por semana você cobre 5 dias com 2 posts por dia.

## Manutenção

**Token do LinkedIn:** dura cerca de 60 dias. Quando faltar menos de 7 dias, o `publish.py` escreve um aviso no `log.txt`. Para renovar, rode `python auth.py` de novo.

**Versão da API:** o LinkedIn lança uma versão por mês e desativa cada uma após cerca de um ano. O `publish.py` detecta automaticamente uma versão ativa, começando pelo mês atual e voltando mês a mês. Para fixar uma versão, edite `LINKEDIN_VERSION` no topo do arquivo (formato `YYYYMM`).

**Hashtags:** use CamelCase sem underline (`#EngenhariaDeDados`, não `#engenharia_de_dados`). O script converte `#Palavra` em hashtag clicável e escapa os caracteres especiais que a API exige.

## Solução de problemas

| Erro | Causa | Solução |
|---|---|---|
| `Not logged in` ou `token expired` | Sem token ou token vencido | `python auth.py` |
| `401 Unauthorized` | Token inválido ou revogado | `python auth.py` |
| `403` / `ACCESS_DENIED` | Produto "Share on LinkedIn" não aprovado ou escopo faltando | Conferir abas Products e Auth do app |
| `426 NONEXISTENT_VERSION` | Versão da API inativa | Já tratado automaticamente; se fixou uma versão, atualize `LINKEDIN_VERSION` |
| `Could not find 'claude' on PATH` | Claude Code não está no PATH do usuário que roda a tarefa | Testar `claude --version` no cmd |
| `redirect_uri mismatch` no login | URL de callback diferente da cadastrada | Cadastrar exatamente `http://localhost:8000/callback` |
| Porta 8000 ocupada no `auth.py` | Outro programa usando a porta | Fechar o programa ou trocar a porta no script e no app |
| Post não saiu no horário | Fila vazia, PC desligado ou erro | Ver `log.txt` e `queue/approved/` |

## Segurança

O `config.json` contém o Client Secret e o token de acesso à sua conta. Não compartilhe nem versione esse arquivo. Se usar Git, crie um `.gitignore`:

```
config.json
log.txt
history.md
queue/
```

Se o secret vazar, gere um novo na aba **Auth** do app e rode `python auth.py` de novo.

## Boas práticas de conteúdo

- Revise tudo antes de aprovar: o post sai com o seu nome.
- Mantenha a seção **"Never"** do `guidelines.md`, que impede o Claude de inventar histórias, clientes ou estatísticas.
- Acompanhe o engajamento nas primeiras semanas.
