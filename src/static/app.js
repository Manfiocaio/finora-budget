// Gráfico de rosca em SVG puro + confirmação de exclusão.
const CORES = ["#1818b7", "#17155e", "#2525ff", "#15803d", "#af7038", "#6768a0",
               "#b91c1c", "#4655ff", "#5b3819", "#737373", "#1d1ae8"];
const brl = new Intl.NumberFormat("pt-BR", { style: "currency", currency: "BRL" });
const NS = "http://www.w3.org/2000/svg";

function desenharGrafico(el) {
  const dados = JSON.parse(el.dataset.dados || "[]");
  const vazio = el.nextElementSibling;
  if (!dados.length) { el.hidden = true; if (vazio) vazio.hidden = false; return; }

  const total = dados.reduce((s, d) => s + d.valor, 0);
  const R = 42, C = 2 * Math.PI * R;
  const svg = document.createElementNS(NS, "svg");
  svg.setAttribute("viewBox", "0 0 120 120");
  svg.setAttribute("role", "img");
  svg.setAttribute("aria-label", "Gráfico de despesas por categoria");

  let acumulado = 0;
  const legenda = document.createElement("ul");
  legenda.className = "legenda";
  dados.forEach((d, i) => {
    const cor = CORES[i % CORES.length];
    const parte = (d.valor / total) * C;
    const c = document.createElementNS(NS, "circle");
    c.setAttribute("cx", 60); c.setAttribute("cy", 60); c.setAttribute("r", R);
    c.setAttribute("fill", "none"); c.setAttribute("stroke", cor); c.setAttribute("stroke-width", 22);
    c.setAttribute("stroke-dasharray", `${parte} ${C - parte}`);
    c.setAttribute("stroke-dashoffset", -acumulado);
    c.setAttribute("transform", "rotate(-90 60 60)");
    svg.appendChild(c);
    acumulado += parte;

    const li = document.createElement("li");
    const marca = document.createElement("i"); marca.style.background = cor;
    const nome = document.createElement("span");
    nome.textContent = `${d.nome} (${Math.round((d.valor / total) * 100)}%)`;
    const valor = document.createElement("span"); valor.textContent = brl.format(d.valor);
    li.append(marca, nome, valor);
    legenda.appendChild(li);
  });
  el.append(svg, legenda);
}

document.querySelectorAll(".grafico").forEach(desenharGrafico);

document.querySelectorAll("form[data-confirmar]").forEach(f =>
  f.addEventListener("submit", e => { if (!confirm(f.dataset.confirmar)) e.preventDefault(); }));
