# Finora Budget

Sistema web simples de controle financeiro pessoal, desenvolvido como trabalho da ETEC.

## Objetivo
Permitir que uma pessoa registre receitas e despesas, acompanhe o saldo, visualize gastos por categoria e acompanhe metas de economia.

## Funcionalidades
1. **Dashboard** – saldo, total de receitas, total de despesas, gráfico de despesas por categoria e movimentações recentes.
2. **Movimentações** – cadastrar, listar, editar e excluir receitas/despesas, com filtro por mês e tipo.
3. **Relatórios** – comparação de receitas × despesas do mês e gráfico de gastos por categoria.
4. **Metas financeiras** – criar, editar e excluir metas, adicionar valores economizados e ver o progresso em % e em barra.

## Tecnologias
Python 3 + Flask · HTML, CSS e JavaScript puro · MySQL (XAMPP) opcional · SQLite local automático para desenvolvimento · `mysql-connector-python` · gráficos em SVG (sem internet).

## Instalação (Windows)
Pré-requisitos: [Python 3.10+](https://www.python.org/downloads/) (marque "Add Python to PATH") e [XAMPP](https://www.apachefriends.org/).

```bat
cd finora-budget
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
copy .env.example .env
```

### Configurar o MySQL no XAMPP
1. Abra o **XAMPP Control Panel** e clique em **Start** no módulo **MySQL**.
2. Clique em **Admin** (ou acesse http://localhost/phpmyadmin).
3. Na aba **Importar**, escolha o arquivo `database.sql` e clique em **Importar**. Isso cria o banco `finora_budget` e as tabelas `movimentacoes` e `metas`.
4. Abra o arquivo `.env` e confira os dados de conexão. No XAMPP padrão: usuário `root` e senha vazia.
   Se você definiu senha para o MySQL, preencha `DB_PASSWORD`. **Nunca publique o `.env` no GitHub** (ele já está no `.gitignore`).

Se o MySQL não estiver disponível, o app usa automaticamente um banco SQLite local em `finora_budget.db` dentro da pasta do projeto, então ele continua funcionando para desenvolvimento e testes locais.
Para exigir o uso do MySQL do XAMPP, defina `DB_BACKEND=mysql` no `.env`. Com `DB_BACKEND=auto` (padrão), o app usa MySQL quando o servidor e o banco configurado estiverem acessíveis; caso contrário, usa SQLite.

## Execução
```bat
venv\Scripts\activate
python src\main.py
```
Acesse http://127.0.0.1:5000

## Testes
```bat
python -m pytest
```
Os testes (`tests/test_calculos.py`) cobrem conversão de valores, formatação em reais, saldo, percentual de metas e validações. Eles **não** precisam do MySQL. As fórmulas estão em `docs/formulas.md`.

## Estrutura
```text
finora-budget/
├── src/ (main.py, database.py, calculos.py, templates/, static/)
├── tests/test_calculos.py
├── docs/formulas.md
├── database.sql  ·  requirements.txt  ·  .env.example  ·  .gitignore  ·  DESIGN.md
```

## Integrantes
- Nome: ______________________
- Nome: ______________________
- Nome: ______________________
- Nome: ______________________

Professor(a): ______________________ · Turma/Módulo: ______________________

## Limitações conhecidas
- Sem login: o sistema é de uso local por uma única pessoa.
- Categorias são uma lista fixa (definida em `src/calculos.py`).
- Os resultados de execução dos testes e a publicação no GitHub devem ser confirmados pela equipe antes da entrega.
