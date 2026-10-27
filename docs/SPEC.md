# ReservaLab API — Especificação

> Fonte única da verdade do projeto. Qualquer mudança de comportamento começa aqui.

API REST para reservar salas e laboratórios do campus. Estudo de caso do seminário
de **Flask-RESTful (Web APIs)** da disciplina TDS — UTFPR.

---

## 1. Stack

| Item | Tecnologia |
|---|---|
| Linguagem | Python 3.12 |
| Framework web | Flask 3.1.3 (testado em servidor real junto com o Flask-RESTful 0.3.10) |
| API REST | Flask-RESTful 0.3.10 |
| Persistência | Flask-SQLAlchemy + SQLite |
| Autenticação | Flask-JWT-Extended |
| Documentação | flasgger (Swagger UI em `/apidocs`, OpenAPI 3.0.3 a partir de `docs/swagger/*.yml`) |
| Testes | pytest + pytest-cov |
| Configuração | python-dotenv |

---

## 2. Entidades

### 2.1 Usuario

| Campo | Tipo | Regras |
|---|---|---|
| id | inteiro | PK |
| nome | texto | obrigatório |
| email | texto | obrigatório, **único** |
| senha_hash | texto | nunca exposto na API |
| papel | enum | `aluno` \| `professor` \| `admin` |
| criado_em | datetime | preenchido automaticamente |

### 2.2 Sala

| Campo | Tipo | Regras |
|---|---|---|
| id | inteiro | PK |
| codigo | texto | obrigatório, **único** (ex.: `LAB-B204`) |
| nome | texto | obrigatório |
| bloco | texto | obrigatório |
| tipo | enum | `laboratorio` \| `sala_aula` \| `auditorio` |
| capacidade | inteiro | > 0 |
| recursos | lista de textos | ex.: `["projetor", "ar-condicionado"]`; armazenada como texto separado por vírgula |
| ativa | bool | padrão `true` |

### 2.3 Reserva

| Campo | Tipo | Regras |
|---|---|---|
| id | inteiro | PK |
| sala_id | inteiro | FK → Sala |
| usuario_id | inteiro | FK → Usuario |
| inicio | datetime | obrigatório |
| fim | datetime | obrigatório |
| participantes | inteiro | > 0 |
| finalidade | texto curto | obrigatório |
| status | enum | `confirmada` \| `cancelada` |
| criado_em | datetime | preenchido automaticamente |

### 2.4 Datas

- Formato **ISO 8601 sem fuso**: `2026-11-10T14:00:00`.
- Interpretadas como **horário local do campus** (datetimes "ingênuos", sem timezone).

### 2.5 Ids

- As três tabelas usam `AUTOINCREMENT` do SQLite (`sqlite_autoincrement=True`): um id excluído **nunca é reaproveitado**, então um `Location` antigo não passa a apontar para outro recurso.
- Bancos criados antes dessa mudança precisam ser **recriados**: apague `instance/reservalab.db` e rode `flask --app app init-db` (ou direto o `seed`). O `create_all` não altera tabelas que já existem.
- O `flask seed` termina imprimindo `Dia da demo: AAAA-MM-DD`: o primeiro dia útil das reservas de exemplo (as encostadas do LAB-B204).
- O seed é idempotente: usuários e salas são buscados pela chave única, e as reservas de exemplo só são criadas num banco **sem reservas** (as datas são relativas a hoje; rodar de novo em outro dia não cria um segundo conjunto). Se o dia da demo já passou, o seed avisa para recriar o banco.

---

## 3. Regras de negócio

| Regra | Descrição | HTTP |
|---|---|---|
| **R1** | `fim` deve ser depois de `inicio`; duração mínima **30 min** e máxima **4 h**. | 400 |
| **R2** | Não é possível reservar no passado (`inicio < agora`). | 400 |
| **R3** | Horário de funcionamento **07:30–22:30**: `inicio >= 07:30` e `fim <= 22:30` (terminar às 22:30 em ponto é permitido); `inicio` e `fim` no **mesmo dia**. | 400 |
| **R4** | Sem sobreposição: conflita com reserva **confirmada** da mesma sala quando `novo.inicio < existente.fim` **E** `novo.fim > existente.inicio`. Horários encostados (um termina 10:00, outro começa 10:00) **não** conflitam. O corpo da resposta traz os dados da reserva conflitante. | 409 |
| **R5** | `participantes` não pode passar da `capacidade` da sala. | 422 |
| **R6** | Sala inativa não pode ser reservada. | 422 |
| **R7** | Auditório só pode ser reservado por `professor` ou `admin`. | 403 |
| **R8** | Aluno pode ter no máximo **3 reservas futuras confirmadas** (`inicio > agora`; canceladas não contam). Professor e admin não têm limite. | 422 |
| **R9** | Cancelar reserva: só o **dono** ou **admin**; não apaga, muda `status` para `cancelada`. Quem não é dono nem admin recebe **404** (como no GET), para não revelar que a reserva existe. Reserva já cancelada ou já iniciada não pode ser cancelada (409). | 204 / 404 / 409 |
| **R10** | Salas: criar, editar e excluir só `admin` (outros papéis → 403). Excluir sala com reservas confirmadas que ainda não terminaram (futuras ou em andamento, `fim > agora`) → 409. Sem elas, a exclusão é permitida e as reservas passadas e canceladas da sala são apagadas junto (cascade no relacionamento `Sala.reservas`). | 204 / 403 / 409 |
| **R11** | Registro público sempre cria papel `aluno` (ninguém se autopromove). | — |

---

## 4. Endpoints

Prefixo: **`/api/v1`**

| Método | Rota | Acesso | Sucesso |
|---|---|---|---|
| GET | `/health` | público | 200 |
| POST | `/auth/registro` | público | 201 |
| POST | `/auth/login` | público | 200 com `access_token` |
| GET | `/usuarios/me` | autenticado | 200 |
| GET | `/salas` | público; filtros `tipo`, `bloco`, `capacidade_min`, `recurso`, `ativa`; paginação | 200 |
| POST | `/salas` | admin | 201 + cabeçalho `Location` |
| GET | `/salas/<id>` | público | 200 |
| PUT | `/salas/<id>` | admin | 200 |
| DELETE | `/salas/<id>` | admin | 204 |
| GET | `/salas/<id>/disponibilidade?data=AAAA-MM-DD` | público | 200 com faixas ocupadas e livres do dia |
| GET | `/reservas` | autenticado; aluno/professor veem só as suas, admin vê todas; filtros `sala_id`, `data`, `status`; paginação | 200 |
| POST | `/reservas` | autenticado | 201 + cabeçalho `Location` |
| GET | `/reservas/<id>` | dono ou admin (outros → 404) | 200 |
| DELETE | `/reservas/<id>` | dono ou admin (outros → 404) | 204 (cancela — ver R9) |

### 4.1 Paginação

- Parâmetros: `page` e `per_page` (padrão **10**, máximo **50**).
- `per_page` acima de 50 é reduzido a 50 em silêncio.
- `page` ou `per_page` menor que 1 ou não numérico → **400**.
- Formato da resposta:

```json
{
  "itens": [ ... ],
  "pagina": 1,
  "por_pagina": 10,
  "total": 23,
  "paginas": 3
}
```

### 4.2 Autenticação

- **Registro** (`POST /auth/registro`): `nome`, `email` e `senha` obrigatórios; senha com no mínimo 6 caracteres; e-mail validado e salvo em minúsculas. E-mail repetido → **409**. Campo `papel` enviado é ignorado (R11). Resposta 201 com o usuário (sem `senha_hash`).
- **Login** (`POST /auth/login`): credenciais inválidas → **401** com mensagem genérica (`"E-mail ou senha inválidos."`), sem revelar se o e-mail existe. Sucesso:

```json
{ "access_token": "<jwt>", "token_type": "Bearer", "expira_em_min": 60 }
```

- O token leva `sub` = id do usuário (texto) e o claim adicional `papel`. Validade padrão de 60 min, configurável por `JWT_EXPIRA_MIN` no `.env`.
- Rotas protegidas recebem o cabeçalho `Authorization: Bearer <token>`. Token ausente, inválido ou expirado → **401**.
- `papel_requerido(*papeis)` (`app/auth.py`) lê o claim `papel`; papel não permitido → **403**.
- Login com e-mail em formato inválido → **400** com a mensagem do campo (validação do `reqparse`, antes de conferir credenciais).
- `GET /usuarios/me` com token de um usuário que não existe mais → **404** `{"message": "Usuário não encontrado."}`.

### 4.3 Salas

Formato de uma sala na resposta:

```json
{
  "id": 1, "codigo": "LAB-B204", "nome": "Laboratório de Programação", "bloco": "B",
  "tipo": "laboratorio", "capacidade": 40,
  "recursos": ["computadores", "projetor", "ar-condicionado"],
  "ativa": true, "url": "/api/v1/salas/1"
}
```

- `url` é o link para a própria sala (`fields.Url`).
- **Entrada (POST e PUT)**: corpo JSON com `codigo`, `nome`, `bloco`, `tipo` e `capacidade` obrigatórios; `recursos` é uma lista JSON de textos sem vírgula (padrão `[]`; item com vírgula → 400, porque a lista é guardada separada por vírgulas); `ativa` é booleano (padrão `true`). `codigo` é salvo em maiúsculas. `tipo` fora de `laboratorio | sala_aula | auditorio` ou `capacidade` que não seja inteiro > 0 → 400.
- **POST** → 201 com `Location: /api/v1/salas/<id>`. Código já usado → **409**.
- **PUT** substitui todos os campos editáveis: campo opcional omitido volta ao padrão (`recursos: []`, `ativa: true`). Manter o próprio código é permitido; usar o código de outra sala → 409.
- **DELETE** → 204 sem corpo; ver R10.
- Sala inexistente (em qualquer rota) → 404 `{"message": "Sala <id> não encontrada."}`.

Filtros de `GET /salas` (query string, todos opcionais e combináveis):

| Parâmetro | Regra |
|---|---|
| `tipo` | igual a um dos tipos válidos |
| `bloco` | igual, sem diferenciar maiúsculas |
| `capacidade_min` | inteiro > 0; `capacidade >= capacidade_min` |
| `recurso` | a sala tem esse item na lista (item inteiro, sem diferenciar maiúsculas: `som` não casa com `sonorizacao`) |
| `ativa` | `true`/`false` (ou `1`/`0`); sem o filtro, lista ativas e inativas |

- Ordenação por `codigo`. Parâmetro inválido (tipo desconhecido, número não inteiro ou < 1, booleano inválido) → **400** `{"message": {"<parametro>": "explicação"}}`. Parâmetros desconhecidos são ignorados.
- `page` além da última página → 200 com `itens` vazio.

### 4.4 Disponibilidade

`GET /salas/<id>/disponibilidade?data=AAAA-MM-DD` — `data` obrigatória; ausente ou em outro formato → 400.

```json
{
  "sala": { "id": 1, "codigo": "LAB-B204", "nome": "Laboratório de Programação", "ativa": true, "url": "/api/v1/salas/1" },
  "data": "2026-10-26",
  "ocupado": [ { "inicio": "2026-10-26T08:00:00", "fim": "2026-10-26T10:00:00", "reserva_id": 1 } ],
  "livre":   [ { "inicio": "2026-10-26T07:30:00", "fim": "2026-10-26T08:00:00" },
               { "inicio": "2026-10-26T10:00:00", "fim": "2026-10-26T22:30:00" } ]
}
```

- Janela de 07:30 a 22:30; só reservas **confirmadas** ocupam a sala; faixas em ordem de horário.
- Reservas encostadas aparecem como faixas ocupadas seguidas, sem faixa livre vazia entre elas.
- Sala inativa: `livre` vem vazia (não pode ser reservada, R6); `ocupado` continua listado.
- O cálculo é a função pura `calcular_faixas` em `app/services/disponibilidade.py`.

### 4.5 Reservas

Entrada do `POST /reservas` (corpo JSON, todos obrigatórios):

| Campo | Formato |
|---|---|
| `sala_id` | inteiro > 0 |
| `inicio`, `fim` | ISO 8601 sem fuso (`2026-11-10T14:00:00`); com fuso → 400 |
| `participantes` | inteiro > 0 |
| `finalidade` | texto não vazio, até 120 caracteres |

Formato de uma reserva na resposta:

```json
{
  "id": 7,
  "sala": { "id": 1, "codigo": "LAB-B204", "nome": "Laboratório de Programação" },
  "usuario": { "id": 3, "nome": "Alice Aluna" },
  "inicio": "2026-11-10T14:00:00", "fim": "2026-11-10T16:00:00",
  "participantes": 5, "finalidade": "Estudo em grupo", "status": "confirmada",
  "criado_em": "2026-10-25T22:10:00", "url": "/api/v1/reservas/7"
}
```

**Ordem de validação** na criação (a primeira regra violada define a resposta):

| # | Verificação | HTTP |
|---|---|---|
| 1 | Formato dos campos (reqparse) | 400 |
| 2 | R1 duração → R2 passado → R3 horário de funcionamento | 400 |
| 3 | Sala existe | 404 |
| 4 | R6 sala inativa | 422 |
| 5 | R7 auditório só professor/admin | 403 |
| 6 | R5 capacidade | 422 |
| 7 | R8 limite do aluno | 422 |
| 8 | R4 conflito de horário | 409 |

- **POST** → 201 com `Location: /api/v1/reservas/<id>`.
- **409 de conflito (R4)** traz a reserva conflitante (a de `inicio` mais cedo, se houver mais de uma), sem dizer quem a fez:

```json
{
  "message": "A sala já está reservada nesse horário.",
  "conflito": { "id": 9, "inicio": "2026-11-10T14:00:00", "fim": "2026-11-10T16:00:00" }
}
```

- **GET `/reservas/<id>` e DELETE** de reserva de outro usuário (quem não é admin) → **404** `{"message": "Reserva <id> não encontrada."}`, a mesma resposta de um id inexistente, para não revelar que a reserva existe.
- **DELETE** (R9): ordem 404 (não é dono nem admin) → 409 já cancelada → 409 já iniciada (`inicio <= agora`, inclui reservas em andamento e passadas) → 204 sem corpo, com `status` mudando para `cancelada`.

Filtros de `GET /reservas` (todos opcionais; aluno e professor sempre limitados às próprias reservas, admin vê todas):

| Parâmetro | Regra |
|---|---|
| `sala_id` | inteiro > 0 |
| `data` | `AAAA-MM-DD`; reservas cujo `inicio` cai nesse dia |
| `status` | `confirmada` ou `cancelada`; sem o filtro, ambas |
| `page`, `per_page` | como na seção 4.1 |

- Ordenação por `inicio` (desempate por `id`). Parâmetro inválido → 400 `{"message": {"<parametro>": "explicação"}}`.
- O "agora" das regras vem de `app/services/relogio.py::agora()`, substituível nos testes.

---

## 5. Formato de erros

Mantém o formato **nativo do Flask-RESTful**. Todas as mensagens em **português**.

| Situação | Formato |
|---|---|
| Erro geral (`abort`) | `{"message": "Sala 1 não encontrada."}` |
| Validação do `reqparse` | `{"message": {"campo": "explicação"}}` |
| Erros do JWT (token ausente, inválido, expirado) | `{"message": "..."}` (mesma chave `message`) |

Erros de formato, tratados por error handlers (`app/erros.py`), sempre em JSON:

| Situação | HTTP | Corpo |
|---|---|---|
| JSON malformado | 400 | `{"message": "Requisição inválida: verifique se o corpo é um JSON válido."}` |
| Rota inexistente | 404 | `{"message": "Recurso não encontrado."}` |
| Método não permitido na rota | 405 | `{"message": "Método não permitido."}` |
| Corpo que não é JSON | 415 | `{"message": "Envie o corpo da requisição como JSON (Content-Type: application/json)."}` |
| Erro interno | 500 | `{"message": "Erro interno do servidor."}` |

Mensagens passadas explicitamente em `abort(código, message=...)` têm prioridade sobre essas.

Regras de entrada válidas para todos os endpoints:

| Situação | HTTP | Corpo |
|---|---|---|
| Corpo JSON válido que não é objeto (lista, texto, número) | 400 | `{"message": "Requisição inválida: o corpo deve ser um objeto JSON ({...})."}` |
| `null` em qualquer campo do corpo (inclusive itens de `recursos`) | 400 | `{"message": {"<campo>": "explicação"}}` |
| Campo inteiro com `true`/`false` ou decimal com casas (`12.7`); `12.0` é aceito como 12 | 400 | idem |
| Inteiro acima de 2⁶³−1 (limite do SQLite) no corpo ou na query string | 400 | idem |
| Id acima de 2⁶³−1 na URL (`/salas/<id>`, `/reservas/<id>`) | 404 | `{"message": "Recurso não encontrado."}` |

---

## 6. Arquitetura

Separação didática em camadas: **HTTP** (resources) → **regras** (services) → **dados** (models).

```
app/
├── __init__.py      # create_app(config): application factory; cria a Api e registra as rotas
├── config.py        # classes de configuração
├── extensions.py    # instâncias de db e jwt
├── auth.py          # decorator papel_requerido("admin", ...) e callbacks do JWT
├── comandos.py      # flask init-db e flask seed
├── swagger.py       # Swagger UI montado a partir de docs/swagger/*.yml
├── erros.py         # mensagens de erro padrão em português (400, 404, 405, 415, 500)
├── parsers.py       # RequestParsers (reqparse)
├── campos.py        # dicionários de fields para marshal_with
├── models/          # um arquivo por entidade (usuario.py, sala.py, reserva.py)
├── resources/       # classes Resource: lê a entrada, chama o serviço, devolve a resposta
└── services/        # regras de negócio, sem nada de HTTP (relogio.py: agora())
tests/
docs/
README.md
```

| Camada | Responsabilidade | Não deve |
|---|---|---|
| `resources/` | Ler entrada (parsers), chamar serviço, serializar (`marshal_with`), escolher código HTTP | Conter regra de negócio |
| `services/` | Aplicar R1–R11, consultar/gravar via models | Importar `flask`, `flask_restful` ou `request`; montar respostas HTTP |
| `models/` | Mapeamento ORM | Conter regra de negócio |

Exceções de negócio: os serviços sinalizam regra violada com exceções próprias. Nas reservas, `RegraViolada(status, mensagem)` carrega o código que a seção 3 associa à regra (um número, sem nada de Flask) e `ConflitoReserva` carrega a reserva conflitante; só o Resource (`traduzir_erros`) transforma isso em resposta com `abort`.

Comandos CLI: `flask init-db` (cria as tabelas) e `flask seed` (dados de exemplo).

---

## 7. Objetivo didático

Cada conceito do Flask-RESTful deve aparecer num **trecho curto, fácil de mostrar em slide**:

| Conceito | Onde aparece |
|---|---|
| `Resource` | `app/resources/` |
| `Api.add_resource` | `app/__init__.py` |
| `reqparse` | `app/parsers.py` |
| `fields` / `marshal_with` | `app/campos.py` + resources |
| `abort` | resources |
| Códigos HTTP | resources (201 + `Location`, 204, 400, 401, 403, 404, 409, 422) |

Comentários curtos em português explicando o **porquê** nos pontos-chave; nada de comentário óbvio.
