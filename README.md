# Finora Budget

Sistema web de controle financeiro pessoal com contas individuais, desenvolvido como trabalho da ETEC.

## Objetivo
Permitir que cada usuário registre receitas e despesas, acompanhe o saldo, visualize gastos por categoria e acompanhe metas de economia.

## Funcionalidades
1. **Dashboard** – saldo disponível após despesas e aplicações, totais de receitas/despesas, carteira investida, gráfico por categoria e movimentações recentes.
2. **Movimentações** – cadastrar, listar, editar e excluir receitas/despesas, com filtro por mês e tipo.
3. **Relatórios** – saldo disponível em gráfico de barras ou linhas, com períodos rápidos e intervalo de datas personalizado, além de despesas por categoria.
4. **Metas financeiras** – acompanhar o valor economizado manualmente ou vincular uma meta ao saldo disponível atualizado automaticamente.
5. **Investimentos** – registrar aplicações de renda fixa, instituição, indexador, taxa e vencimento; acompanhar e registrar resgates parciais.
6. **Orçamentos mensais** – definir limites por categoria e acompanhar gasto, percentual utilizado e valor restante ou excedido.
7. **Movimentações recorrentes** – agendar receitas e despesas semanais, quinzenais ou mensais, com lançamentos automáticos, pausa e data final opcional.
8. **Perfil da conta** – editar nome e foto, com resumo de movimentações, metas, saldo e carteira.
9. **Contas individuais** – cadastro por e-mail, login/logout e dados financeiros separados por usuário.

## Tecnologias
Python 3 + Flask · HTML, CSS e JavaScript puro · MySQL (XAMPP) opcional · SQLite local automático para desenvolvimento · `mysql-connector-python` · Pillow para processamento seguro de fotos de perfil · gráficos em SVG (sem internet).

## Instalação (Windows)
Pré-requisito: [Python 3.10+](https://www.python.org/downloads/) (marque "Add Python to PATH"). O XAMPP é opcional: sem MySQL configurado, o projeto funciona com SQLite.

```bat
git clone https://github.com/Manfiocaio/finora-budget.git
cd finora-budget
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
copy .env.example .env
```

O arquivo `.env` é local e ignorado pelo Git. Para manter as sessões válidas após reiniciar o app, gere uma chave com `python -c "import secrets; print(secrets.token_hex(32))"` e copie o resultado para `SECRET_KEY` no `.env`. Para usar SQLite mesmo que haja MySQL instalado, configure `DB_BACKEND=sqlite`.

### Configurar o MySQL no XAMPP
1. Abra o **XAMPP Control Panel** e clique em **Start** no módulo **MySQL**.
2. Clique em **Admin** (ou acesse http://localhost/phpmyadmin).
3. Na aba **Importar**, escolha o arquivo `database.sql` e clique em **Importar**. Isso cria o banco `finora_budget` e suas tabelas.
4. Abra o arquivo `.env` e confira os dados de conexão. No XAMPP padrão: usuário `root` e senha vazia.
   Se você definiu senha para o MySQL, preencha `DB_PASSWORD`. **Nunca publique o `.env` no GitHub** (ele já está no `.gitignore`).

Se o MySQL não estiver disponível, o app usa automaticamente um banco SQLite local chamado `finora_budget.db` na raiz do projeto. Esse banco contém dados locais e é ignorado pelo Git.
Para exigir o uso do MySQL do XAMPP, defina `DB_BACKEND=mysql` no `.env`. Com `DB_BACKEND=auto` (padrão), o app usa MySQL quando o servidor e o banco configurado estiverem acessíveis; caso contrário, usa SQLite.
Ao iniciar em um banco existente, o app adiciona a estrutura de contas e colunas de proprietário. Registros anteriores, sem usuário associado, permanecem preservados, mas ocultos das contas novas.

### Contas
Na primeira visita, crie uma conta usando **Criar conta**. Após criar a conta, informe como prefere ser chamado; esse nome aparece na saudação personalizada do painel e na navegação. O perfil, acessível pelo avatar da barra lateral, permite mudar o nome e enviar/remover uma foto. O editor de foto permite arrastar, ampliar e enquadrar a imagem antes de salvá-la; imagens são redimensionadas e guardadas por conta. Login e cadastro têm controles para mostrar/ocultar a senha. Cada conta exige um e-mail válido e senha com pelo menos 8 caracteres. Movimentações, metas e investimentos são vinculados à conta autenticada e não aparecem para outros usuários. O logout encerra a sessão; formulários de alteração também usam proteção CSRF.

Nos relatórios, o gráfico de saldo disponível alterna entre barras e linha, com períodos de 1 dia a 10 anos, histórico completo ou intervalo personalizado. É possível informar apenas uma data para consultar um único dia.

### Orçamentos e recorrências
Em **Planejamento**, configure um limite mensal para cada categoria de despesa. O Finora compara o limite ao total de despesas lançadas naquela categoria no mês selecionado; o orçamento permanece configurado nos meses seguintes. Na página de movimentações recorrentes, é possível agendar receitas ou despesas para cada semana, a cada duas semanas ou mensalmente, com encerramento opcional. O servidor verifica os agendamentos automaticamente a cada minuto e também ao atender uma solicitação autenticada; datas vencidas são recuperadas em ordem e processadas em transação para impedir lançamentos duplicados, inclusive se o servidor reiniciar ou várias solicitações coincidirem. O agendador roda no processo iniciado por `python src\main.py`.

### Metas e investimentos
Uma conta pode vincular uma única meta ao saldo disponível; esse valor é calculado dinamicamente como receitas menos despesas e o principal ainda investido. Aplicações reduzem o saldo disponível sem serem contabilizadas como despesas, e resgates registrados aumentam a disponibilidade. A carteira guarda o principal informado, sem projetar rentabilidade nem substituir o saldo atualizado pela instituição financeira.

Mantenha `SECRET_KEY` privada e estável no `.env` para que as sessões permaneçam válidas entre reinicializações. Em produção com HTTPS, configure `SESSION_COOKIE_SECURE=1`; para execução local em HTTP, mantenha `0`.

## Execução
```bat
.venv\Scripts\activate
python src\main.py
```
Acesse http://127.0.0.1:5000

## Testes
```bat
python -m pytest
```
Os testes (`tests/test_calculos.py`, `tests/test_database.py` e `tests/test_planning.py`) cobrem conversão e validações, persistência SQLite, autenticação, isolamento entre contas, metas vinculadas, carteira, orçamentos, recorrências, concorrência e proteção CSRF. Eles **não** precisam do MySQL. As fórmulas estão em `docs/formulas.md`.

## Estrutura
```text
finora-budget/
├── src/ (main.py, database.py, calculos.py, templates/, static/)
├── tests/ (test_calculos.py, test_database.py, test_planning.py)
├── docs/formulas.md
├── README.md  ·  requirements.txt  ·  .env.example  ·  .gitignore
├── database.sql  ·  DESIGN.md
```

## Integrantes
- Caio Manfio
- Caio Fichel
- Enzo Matiello

## Limitações conhecidas
- O cadastro é aberto, sem confirmação de e-mail nem recuperação de senha; adequado para uso local/ambiente de demonstração.
- Categorias são uma lista fixa (definida em `src/calculos.py`).
- O servidor de desenvolvimento Flask não deve ser exposto diretamente à internet; publique em produção apenas com um servidor WSGI e HTTPS configurados.
- Antes da entrega, a equipe deve confirmar que o repositório e o histórico Git não contêm dados privados.
