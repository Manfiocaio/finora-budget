// Gráficos SVG, editor de foto de perfil e confirmação de exclusão.
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

function svgElemento(nome, atributos, texto) {
  const el = document.createElementNS(NS, nome);
  Object.entries(atributos).forEach(([chave, valor]) => el.setAttribute(chave, valor));
  if (texto) el.textContent = texto;
  return el;
}

function desenharEvolucao(el) {
  el.replaceChildren();
  const dados = JSON.parse(el.dataset.dados || "[]");
  const vazio = el.nextElementSibling;
  if (!dados.length) {
    el.hidden = true;
    if (vazio) vazio.hidden = false;
    return;
  }
  el.hidden = false;
  if (vazio) vazio.hidden = true;

  const linhas = el.dataset.tipo === "linhas";
  const largura = 900, altura = 390, esquerda = 96, direita = 884, topo = 28, base = 324;
  const minDado = Math.min(...dados.map(d => Math.min(d.minima, d.abertura, d.fechamento)));
  const maxDado = Math.max(...dados.map(d => Math.max(d.maxima, d.abertura, d.fechamento)));
  const intervalo = maxDado - minDado;
  const margem = intervalo ? intervalo * .1 : Math.max(Math.abs(maxDado) * .05, 1);
  const minimo = minDado < 0 ? minDado - margem : 0;
  let maximo = maxDado > 0 ? maxDado + margem : 0;
  if (minimo === maximo) maximo += 1;
  const y = valor => base - ((valor - minimo) / (maximo - minimo)) * (base - topo);
  const tempos = dados.map(d => new Date(`${d.data}T12:00:00`).getTime());
  const duracao = tempos[tempos.length - 1] - tempos[0];
  const x = i => duracao
    ? esquerda + ((tempos[i] - tempos[0]) / duracao) * (direita - esquerda)
    : (esquerda + direita) / 2;
  const svg = svgElemento("svg", {
    viewBox: `0 0 ${largura} ${altura}`,
    role: "img",
    "aria-label": `Gráfico de ${linhas ? "linha" : "barras"} da evolução do saldo disponível, de ${dados[0].data} a ${dados[dados.length - 1].data}`
  });
  const compactCurrency = new Intl.NumberFormat("pt-BR", {
    style: "currency", currency: "BRL", notation: "compact", maximumFractionDigits: 1
  });
  const currencyForAxis = value => compactCurrency.format(value).replace(/\s/g, "");
  for (let i = 0; i <= 4; i++) {
    const value = maximo - (maximo - minimo) * i / 4;
    const posicaoY = y(value);
    svg.appendChild(svgElemento("line", {
      x1: esquerda, x2: direita, y1: posicaoY, y2: posicaoY, class: "evolucao-grade"
    }));
    svg.appendChild(svgElemento("text", {
      x: esquerda - 12, y: posicaoY + 4, "text-anchor": "end", class: "evolucao-eixo"
    }, currencyForAxis(value)));
  }

  if (linhas) {
    const pontos = dados.map((d, i) => `${x(i)},${y(d.fechamento)}`).join(" ");
    svg.appendChild(svgElemento("polyline", {
        points: pontos,
        fill: "none",
        stroke: "#2525ff",
        "stroke-width": 3.5,
        "stroke-linecap": "round",
        "stroke-linejoin": "round",
        class: "evolucao-linha"
    }));
    dados.forEach((d, i) => {
      const ponto = svgElemento("circle", {
        cx: x(i), cy: y(d.fechamento), r: 4.5, fill: "#2525ff", class: "evolucao-ponto"
      });
      ponto.appendChild(svgElemento("title", {}, `${formatarDataGrafico(d.data, el.dataset.granularidade)} · Saldo: ${brl.format(d.fechamento)}`));
      svg.appendChild(ponto);
    });
  } else {
    const larguraBarra = Math.max(3, Math.min(22, (direita - esquerda) / Math.max(dados.length, 1) * .58));
    dados.forEach((d, i) => {
      const centro = x(i);
      const saldoAnterior = i ? dados[i - 1].fechamento : d.abertura;
      const classe = d.fechamento >= saldoAnterior ? "barra-evolucao-alta" : "barra-evolucao-baixa";
      const topoBarra = Math.min(y(0), y(d.fechamento));
      const alturaBarra = Math.max(2, Math.abs(y(d.fechamento) - y(0)));
      const barra = svgElemento("rect", {
        x: centro - larguraBarra / 2, y: topoBarra, width: larguraBarra,
        height: alturaBarra, rx: 2, class: `evolucao-barra ${classe}`
      });
      barra.appendChild(svgElemento("title", {}, [
        formatarDataGrafico(d.data, el.dataset.granularidade),
        `Saldo disponível: ${brl.format(d.fechamento)}`
      ].join(" · ")));
      svg.appendChild(barra);
    });
  }
  const total = dados.length;
  const intervaloRótulo = Math.max(1, Math.ceil(total / 7));
  dados.forEach((d, i) => {
    if (i % intervaloRótulo !== 0 && i !== total - 1) return;
    svg.appendChild(svgElemento("text", {
      x: x(i), y: 350, "text-anchor": "middle", class: "evolucao-label"
    }, formatarDataGrafico(d.data, el.dataset.granularidade)));
  });
  el.appendChild(svg);

  const legenda = document.createElement("ul");
  legenda.className = "legenda legenda-evolucao";
  const itensLegenda = linhas
    ? [["linha", "Saldo no fechamento"]]
    : [["barra-alta", "Saldo subiu"], ["barra-baixa", "Saldo caiu"]];
  itensLegenda.forEach(([classe, texto]) => {
    const item = document.createElement("li");
    const marca = document.createElement("i");
    marca.className = `marca-grafico marca-${classe}`;
    const legendaTexto = document.createElement("span");
    legendaTexto.textContent = texto;
    item.append(marca, legendaTexto);
    legenda.appendChild(item);
  });
  el.appendChild(legenda);
}

function formatarDataGrafico(valor, granularidade) {
  const data = new Date(`${valor}T12:00:00`);
  const opcoes = granularidade === "mês"
    ? { month: "short", year: "2-digit" }
    : { day: "2-digit", month: "short" };
  return new Intl.DateTimeFormat("pt-BR", opcoes).format(data).replace(".", "");
}

document.querySelectorAll(".grafico-evolucao").forEach(desenharEvolucao);

document.querySelectorAll("[data-tipo-grafico]").forEach(botao => {
  botao.addEventListener("click", () => {
    const grupo = botao.closest(".card");
    const grafico = grupo.querySelector(".grafico-evolucao");
    grupo.querySelectorAll("[data-tipo-grafico]").forEach(opcao => {
      const selecionado = opcao === botao;
      opcao.setAttribute("aria-pressed", String(selecionado));
      opcao.classList.toggle("ativo", selecionado);
    });
    grafico.dataset.tipo = botao.dataset.tipoGrafico;
    desenharEvolucao(grafico);
  });
});

const periodoGrafico = document.querySelector("[data-periodo-grafico]");
if (periodoGrafico) {
  periodoGrafico.addEventListener("change", () => {
    if (periodoGrafico.value !== "personalizado") {
      document.querySelectorAll("[data-data-grafico]").forEach(campo => { campo.value = ""; });
    }
  });
  document.querySelectorAll("[data-data-grafico]").forEach(campo => {
    campo.addEventListener("change", () => { periodoGrafico.value = "personalizado"; });
  });
}

const entradaFoto = document.getElementById("foto");
const modalRecorte = document.querySelector("[data-modal-recorte]");
if (entradaFoto && modalRecorte) {
  const imagemRecorte = modalRecorte.querySelector("[data-imagem-recorte]");
  const palco = modalRecorte.querySelector("[data-palco-recorte]");
  const zoom = modalRecorte.querySelector("#zoom-foto");
  const erroForaModal = document.querySelector("[data-perfil-erro]");
  const erroFoto = document.createElement("p");
  erroFoto.className = "recorte-erro";
  erroFoto.setAttribute("role", "alert");
  erroFoto.hidden = true;
  modalRecorte.querySelector(".recorte-ajuda").after(erroFoto);
  let urlOriginal = null;
  let urlPreviaConfirmada = null;
  let arquivoConfirmado = entradaFoto.files[0] || null;
  let escalaBase = 1;
  let escalaAtual = 1;
  let posicaoX = 0;
  let posicaoY = 0;
  let arrasto = null;

  const informarErroFoto = mensagem => {
    if (modalRecorte.open) {
      erroFoto.textContent = mensagem;
      erroFoto.hidden = false;
    } else if (erroForaModal) {
      erroForaModal.textContent = mensagem;
      erroForaModal.hidden = false;
    }
  };
  const atualizarImagem = () => {
    const largura = imagemRecorte.naturalWidth * escalaBase * escalaAtual;
    const altura = imagemRecorte.naturalHeight * escalaBase * escalaAtual;
    const retangulo = palco.getBoundingClientRect();
    posicaoX = Math.min(0, Math.max(retangulo.width - largura, posicaoX));
    posicaoY = Math.min(0, Math.max(retangulo.height - altura, posicaoY));
    imagemRecorte.style.width = `${largura}px`;
    imagemRecorte.style.height = `${altura}px`;
    imagemRecorte.style.left = `${posicaoX}px`;
    imagemRecorte.style.top = `${posicaoY}px`;
  };
  const restaurarArquivoConfirmado = () => {
    const transferencia = new DataTransfer();
    if (arquivoConfirmado) transferencia.items.add(arquivoConfirmado);
    entradaFoto.files = transferencia.files;
  };
  const fecharRecorte = confirmar => {
    if (!confirmar) {
      restaurarArquivoConfirmado();
      if (urlOriginal) URL.revokeObjectURL(urlOriginal);
      urlOriginal = null;
      modalRecorte.close();
      return;
    }
    const tamanho = palco.getBoundingClientRect().width;
    const escala = escalaBase * escalaAtual;
    const recorteX = Math.max(0, -posicaoX / escala);
    const recorteY = Math.max(0, -posicaoY / escala);
    const lado = Math.min(imagemRecorte.naturalWidth - recorteX, tamanho / escala);
    const canvas = document.createElement("canvas");
    canvas.width = 256;
    canvas.height = 256;
    const contexto = canvas.getContext("2d");
    if (!contexto) {
      informarErroFoto("Não foi possível preparar a foto neste navegador.");
      return;
    }
    contexto.drawImage(imagemRecorte, recorteX, recorteY, lado, lado, 0, 0, 256, 256);
    canvas.toBlob(blob => {
      if (!blob) {
        informarErroFoto("Não foi possível preparar a foto. Tente outra imagem.");
        return;
      }
      const arquivo = new File([blob], "foto-perfil.webp", { type: "image/webp" });
      const transferencia = new DataTransfer();
      transferencia.items.add(arquivo);
      entradaFoto.files = transferencia.files;
      arquivoConfirmado = arquivo;
      if (urlPreviaConfirmada) URL.revokeObjectURL(urlPreviaConfirmada);
      urlPreviaConfirmada = URL.createObjectURL(blob);
      document.querySelectorAll("[data-avatar-photo]").forEach(avatar => {
        avatar.src = urlPreviaConfirmada;
        avatar.hidden = false;
      });
      document.querySelectorAll("[data-avatar-inicial]").forEach(inicial => { inicial.hidden = true; });
      document.querySelectorAll(".mobile-avatar, .avatar-usuario").forEach(avatar => {
        if (avatar.tagName === "IMG") {
          avatar.src = urlPreviaConfirmada;
        } else {
          const foto = document.createElement("img");
          foto.className = avatar.className;
          foto.src = urlPreviaConfirmada;
          foto.alt = "";
          avatar.replaceWith(foto);
        }
      });
      const removerFoto = document.querySelector('[name="remover_foto"]');
      if (removerFoto) removerFoto.checked = false;
      if (urlOriginal) URL.revokeObjectURL(urlOriginal);
      urlOriginal = null;
      modalRecorte.close();
      document.getElementById("form-perfil").requestSubmit();
    }, "image/webp", .9);
  };

  document.querySelector("[data-escolher-foto]").addEventListener("click", () => entradaFoto.click());
  entradaFoto.addEventListener("change", () => {
    const arquivo = entradaFoto.files[0];
    if (!arquivo) return;
    if (!["image/png", "image/jpeg", "image/webp"].includes(arquivo.type)) {
      informarErroFoto("Escolha uma imagem PNG, JPEG ou WebP.");
      restaurarArquivoConfirmado();
      return;
    }
    if (arquivo.size > 5 * 1024 * 1024) {
      informarErroFoto("A imagem deve ter no máximo 5 MB.");
      restaurarArquivoConfirmado();
      return;
    }
    if (erroForaModal) erroForaModal.hidden = true;
    erroFoto.hidden = true;
    if (urlOriginal) URL.revokeObjectURL(urlOriginal);
    urlOriginal = URL.createObjectURL(arquivo);
    imagemRecorte.onload = () => {
      modalRecorte.showModal();
      const retangulo = palco.getBoundingClientRect();
      escalaBase = Math.max(retangulo.width / imagemRecorte.naturalWidth, retangulo.height / imagemRecorte.naturalHeight);
      escalaAtual = 1;
      zoom.value = "1";
      posicaoX = (retangulo.width - imagemRecorte.naturalWidth * escalaBase) / 2;
      posicaoY = (retangulo.height - imagemRecorte.naturalHeight * escalaBase) / 2;
      atualizarImagem();
    };
    imagemRecorte.onerror = () => {
      restaurarArquivoConfirmado();
      if (urlOriginal) URL.revokeObjectURL(urlOriginal);
      urlOriginal = null;
      informarErroFoto("Não foi possível abrir essa imagem.");
    };
    imagemRecorte.src = urlOriginal;
  });
  zoom.addEventListener("input", () => {
    const centroX = palco.clientWidth / 2;
    const centroY = palco.clientHeight / 2;
    const fator = Number(zoom.value) / escalaAtual;
    posicaoX = centroX - (centroX - posicaoX) * fator;
    posicaoY = centroY - (centroY - posicaoY) * fator;
    escalaAtual = Number(zoom.value);
    atualizarImagem();
  });
  palco.addEventListener("pointerdown", evento => {
    arrasto = { x: evento.clientX, y: evento.clientY, left: posicaoX, top: posicaoY };
    palco.setPointerCapture(evento.pointerId);
  });
  palco.addEventListener("pointermove", evento => {
    if (!arrasto) return;
    posicaoX = arrasto.left + evento.clientX - arrasto.x;
    posicaoY = arrasto.top + evento.clientY - arrasto.y;
    atualizarImagem();
  });
  palco.addEventListener("pointerup", () => { arrasto = null; });
  palco.addEventListener("pointercancel", () => { arrasto = null; });
  modalRecorte.querySelectorAll("[data-cancelar-recorte]").forEach(botao => {
    botao.addEventListener("click", () => fecharRecorte(false));
  });
  modalRecorte.querySelector("[data-aplicar-recorte]").addEventListener("click", () => fecharRecorte(true));
  modalRecorte.addEventListener("cancel", evento => {
    evento.preventDefault();
    fecharRecorte(false);
  });
}

document.querySelectorAll("[data-toggle-senha]").forEach(botao => {
  botao.addEventListener("click", () => {
    const senha = document.getElementById(botao.dataset.toggleSenha);
    const mostrar = senha.type === "password";
    senha.type = mostrar ? "text" : "password";
    botao.setAttribute("aria-pressed", String(mostrar));
    botao.setAttribute("aria-label", mostrar ? "Ocultar senha" : "Mostrar senha");
  });
});

document.querySelectorAll(".check-saldo input").forEach(checkbox => {
  const campo = checkbox.closest("form").querySelector(".campo-acumulado input");
  const atualizar = () => { campo.readOnly = checkbox.checked; };
  checkbox.addEventListener("change", atualizar);
  atualizar();
});

document.querySelectorAll("form[data-confirmar]").forEach(f =>
  f.addEventListener("submit", e => { if (!confirm(f.dataset.confirmar)) e.preventDefault(); }));
