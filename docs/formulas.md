# Fórmulas do Finora Budget

| Indicador | Fórmula | Onde é calculado |
|---|---|---|
| Total de receitas | `SUM(valor)` das movimentações com `tipo = 'receita'` | MySQL (`database.totais`) |
| Total de despesas | `SUM(valor)` das movimentações com `tipo = 'despesa'` | MySQL (`database.totais`) |
| Saldo | `receitas − despesas` | `calculos.calcular_saldo` |
| Gastos por categoria | `SUM(valor)` das despesas agrupado por `categoria` | MySQL (`database.despesas_por_categoria`) |
| Percentual de cada categoria | `valor da categoria ÷ total de despesas × 100` | JavaScript (`static/app.js`) |
| Progresso da meta | `valor acumulado ÷ valor objetivo × 100` (barra limitada a 100%) | `calculos.percentual_meta` |
| Relatório mensal | Mesmas somas, filtradas por `DATE_FORMAT(data, '%Y-%m') = mês escolhido` | MySQL |

Valores monetários usam `DECIMAL(12,2)` no banco e `Decimal` no Python, evitando erros de arredondamento de `float`.
