# DESIGN.md — Finora Budget

> O arquivo `DESIGN.md` original do professor/equipe não foi enviado junto com o prompt.
> Este documento descreve a identidade visual criada para o projeto. Se existir um
> `DESIGN.md` oficial, substitua este arquivo e ajuste `src/static/style.css` (variáveis em `:root`).

## Cores
| Nome | Hex | Uso |
|---|---|---|
| Pinho | `#0B3D33` | Menu lateral e card de saldo (elemento de destaque) |
| Verde Finora | `#0E6B57` | Ações principais, barra de metas |
| Receita | `#13805A` | Valores de entrada |
| Despesa | `#BF4126` | Valores de saída |
| Âmbar | `#D99A1E` | Sinal da marca e foco do teclado |
| Névoa | `#EDF1EF` | Fundo da página |
| Tinta | `#12231F` | Texto |

## Tipografia
Fontes do sistema (Segoe UI no Windows): funciona offline. Números com `tabular-nums`.
Título 1,75rem/650 · seção 1,05rem/600 · corpo 1rem · saldo 2,4rem.

## Princípios
- Um único destaque visual: o saldo em card escuro; o restante é discreto.
- Cards brancos com borda fina, sem sombras.
- Cores semânticas: verde = entrada, vermelho = saída.
- Responsivo: menu lateral no computador; barra superior no celular.
- Foco de teclado visível, confirmação antes de excluir, estados vazios sempre explicados.
