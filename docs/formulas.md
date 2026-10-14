# Fórmulas do Finora Budget

| Indicador | Fórmula | Onde é calculado |
|---|---|---|
| Total de receitas | `SUM(valor)` das movimentações com `tipo = 'receita'` | MySQL (`database.totais`) |
| Total de despesas | `SUM(valor)` das movimentações com `tipo = 'despesa'` | MySQL (`database.totais`) |
| Saldo bruto | `receitas − despesas` | `calculos.calcular_saldo` |
| Saldo disponível | `receitas − despesas − principal ainda investido` | `main._saldo_disponivel` |
| Principal investido | `SUM(saldo_atual)` da carteira | `database.saldo_investido` |
| Aplicações no mês | `SUM(valor_inicial)` pela data da aplicação | `database.investimentos_aplicados_no_mes` |
| Resgates no mês | `SUM(valor)` pela data do resgate | `database.investimentos_resgatados_no_mes` |
| Gastos por categoria | `SUM(valor)` das despesas agrupado por `categoria` | MySQL (`database.despesas_por_categoria`) |
| Percentual de cada categoria | `valor da categoria ÷ total de despesas × 100` | JavaScript (`static/app.js`) |
| Progresso da meta manual | `valor acumulado ÷ valor objetivo × 100` (barra limitada a 100%) | `calculos.percentual_meta` |
| Progresso da meta vinculada | Usa o saldo disponível calculado no momento da consulta | `main._metas_com_progresso` |
| Relatório mensal | Somas de movimentações e da carteira, filtradas pelo mês escolhido | `main.relatorios` |

Valores monetários usam `DECIMAL(12,2)` no banco e `Decimal` no Python, evitando erros de arredondamento de `float`.
