/* Front del Generador de Planogramas.
   El acomodo lo calcula el servidor local; acá solo se dibuja y se controla. */
(function () {
  "use strict";

  var $ = function (s) { return document.querySelector(s); };
  var estado = {
    token: null, hoja: null, categoria: "", datos: null,
    modulo: 0, zoom: 1, ajustar: true, seleccion: null, ocupado: 0
  };

  var el = {
    drop: $("#drop"), archivo: $("#entradaArchivo"), controles: $("#controles"),
    hoja: $("#selHoja"), categoria: $("#txtCategoria"),
    ancho: $("#numAncho"), alto: $("#numAlto"), caras: $("#numCaras"),
    salidaCaras: $("#salidaCaras"), auto: $("#chkAuto"), campoCaras: $("#campoCaras"),
    resumen: $("#resumen"), avisos: $("#avisos"), nombre: $("#archivoActual"),
    tabs: $("#tabsModulos"), lienzo: $("#lienzoScroll"), vacio: $("#vacio"),
    detalle: $("#detalleScroll"), buscador: $("#buscador"),
    btnPdf: $("#btnPdf"), cargando: $("#cargando"), toast: $("#toast")
  };

  /* ------------------------------------------------------------ utilidades */
  function pct(v, total) { return (100 * v / total).toFixed(4) + "%"; }

  function nodo(tag, clase, texto) {
    var n = document.createElement(tag);
    if (clase) n.className = clase;
    if (texto != null) n.textContent = texto;
    return n;
  }

  var temporizadorToast;
  function avisar(mensaje, esError) {
    el.toast.textContent = mensaje;
    el.toast.className = "aviso-flotante" + (esError ? " error" : "");
    el.toast.hidden = false;
    clearTimeout(temporizadorToast);
    temporizadorToast = setTimeout(function () { el.toast.hidden = true; },
                                   esError ? 7000 : 3500);
  }

  // contador, no booleano: cargar() encadena generar() y ambos abren/cierran
  function ocupado(si) {
    estado.ocupado = Math.max(0, estado.ocupado + (si ? 1 : -1));
    el.cargando.hidden = estado.ocupado === 0;
  }

  function pedir(ruta, opciones) {
    return fetch(ruta, opciones).then(function (r) {
      var tipo = r.headers.get("Content-Type") || "";
      if (tipo.indexOf("application/json") === 0) {
        return r.json().then(function (d) {
          if (!r.ok) throw new Error(d.error || "Error " + r.status);
          return d;
        });
      }
      if (!r.ok) throw new Error("Error " + r.status);
      return r.blob();
    });
  }

  function urlImagen(idx) {
    return "/api/img?t=" + encodeURIComponent(estado.token) +
           "&h=" + encodeURIComponent(estado.hoja) + "&i=" + idx;
  }

  /* ------------------------------------------------------------- carga */
  function cargarArchivo(archivo) {
    if (!archivo) return;
    if (!/\.xlsx?$|\.xlsm$/i.test(archivo.name)) {
      avisar("El archivo tiene que ser .xlsx o .xlsm", true);
      return;
    }
    ocupado(true);
    pedir("/api/cargar", {
      method: "POST",
      headers: { "Content-Type": "application/octet-stream", "X-Nombre": archivo.name },
      body: archivo
    }).then(function (d) {
      estado.token = d.token;
      estado.hoja = d.hoja;
      estado.categoria = d.categoria;

      el.hoja.innerHTML = "";
      d.hojas.forEach(function (h) {
        var o = nodo("option", null, h);
        o.value = h;
        el.hoja.appendChild(o);
      });
      el.hoja.value = d.hoja;
      el.hoja.parentElement.hidden = d.hojas.length < 2;
      el.categoria.value = d.categoria;
      el.controles.hidden = false;
      el.drop.classList.add("compacta");
      el.drop.querySelector("strong").textContent = "Cambiar archivo";
      el.drop.querySelector("span").textContent = archivo.name;
      el.nombre.textContent = archivo.name;
      el.nombre.hidden = false;
      generar();
    }).catch(function (e) {
      avisar(e.message, true);
    }).finally(function () { ocupado(false); });
  }

  /* ---------------------------------------------------------- generación */
  function parametros() {
    return {
      token: estado.token,
      hoja: el.hoja.value,
      categoria: el.categoria.value.trim() || el.hoja.value,
      ancho: el.ancho.value,
      alto: el.alto.value,
      caras: el.caras.value,
      auto: el.auto.checked
    };
  }

  var temporizador;
  function generarPronto() {
    clearTimeout(temporizador);
    temporizador = setTimeout(generar, 300);
  }

  function generar() {
    if (!estado.token) return;
    ocupado(true);
    var p = parametros();
    pedir("/api/generar", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(p)
    }).then(function (d) {
      estado.datos = d;
      estado.hoja = d.hoja;
      estado.categoria = p.categoria;
      estado.modulo = Math.min(estado.modulo, d.modulos.length - 1);
      estado.seleccion = null;
      el.btnPdf.disabled = false;
      el.buscador.disabled = false;
      dibujarTabs();
      dibujarPlano();
      dibujarResumen();
      dibujarTabla();
      // recién con la tabla puesta el alto del lienzo es el definitivo
      requestAnimationFrame(function () { requestAnimationFrame(aplicarZoom); });
    }).catch(function (e) {
      avisar(e.message, true);
      el.btnPdf.disabled = true;
    }).finally(function () { ocupado(false); });
  }

  /* -------------------------------------------------------------- módulos */
  function dibujarTabs() {
    el.tabs.innerHTML = "";
    var mods = estado.datos.modulos;
    if (mods.length < 2) return;
    mods.forEach(function (m, i) {
      var b = nodo("button", "tab" + (i === estado.modulo ? " activo" : ""),
                   "Módulo " + m.indice);
      b.onclick = function () { estado.modulo = i; dibujarTabs(); dibujarPlano(); };
      el.tabs.appendChild(b);
    });
  }

  function dibujarResumen() {
    var d = estado.datos, m = d.modulos[estado.modulo];
    el.resumen.innerHTML = "";
    [["Módulos", d.modulos.length], ["Productos", d.productos.length],
     ["Caras en módulo " + m.indice, m.caras], ["Ocupación", m.ocupacion + "%"]
    ].forEach(function (par) {
      var c = nodo("div");
      c.appendChild(nodo("b", null, String(par[1])));
      c.appendChild(nodo("span", null, par[0]));
      el.resumen.appendChild(c);
    });
    el.resumen.hidden = false;

    el.avisos.innerHTML = "";
    if (d.avisos.length) {
      el.avisos.appendChild(nodo("strong", null, "Avisos (" + d.avisos.length + ")"));
      var ul = nodo("ul");
      d.avisos.slice(0, 12).forEach(function (a) { ul.appendChild(nodo("li", null, a)); });
      if (d.avisos.length > 12) ul.appendChild(nodo("li", null, "…"));
      el.avisos.appendChild(ul);
    }
    el.avisos.hidden = !d.avisos.length;
  }

  /* ---------------------------------------------------------------- plano */
  function dibujarPlano() {
    var d = estado.datos, mod = d.modulos[estado.modulo], mu = d.mueble;
    var W = mu.ancho, H = mu.alto;

    el.lienzo.innerHTML = "";
    var caja = nodo("div");

    var plano = nodo("div", "plano");
    var regleta = nodo("div", "regleta");
    var cota = nodo("div", "cota-alto");
    cota.appendChild(nodo("span", null, W + " × " + H + " cm"));
    regleta.appendChild(cota);

    var mueble = nodo("div", "mueble");
    mueble.style.aspectRatio = W + " / " + H;

    // fondos de zona
    if (mod.niveles.some(function (n) { return n.tipo === "gancho"; })) {
      var zp = nodo("div", "zona peg");
      zp.style.bottom = pct(mod.peg_bottom, H);
      zp.style.height = pct(H - mu.cenefa - mod.peg_bottom, H);
      mueble.appendChild(zp);
    }
    if (mod.shelf_top > mu.base) {
      var ze = nodo("div", "zona estante");
      ze.style.bottom = "0";
      ze.style.height = pct(mod.shelf_top, H);
      mueble.appendChild(ze);
    }

    // base y tablillas
    var base = nodo("div", "base");
    base.style.height = pct(mu.base, H);
    mueble.appendChild(base);

    mod.niveles.forEach(function (nv) {
      if (nv.tipo === "tablilla" && nv.tiene_tabla) {
        var t = nodo("div", "tabla-board");
        t.style.bottom = pct(nv.board_y, H);
        t.style.height = pct(mu.espesor, H);
        mueble.appendChild(t);
      }
      if (nv.tipo === "gancho") {
        var b = nodo("div", "barra-gancho");
        b.style.bottom = pct(nv.top_y, H);
        mueble.appendChild(b);
      }
      // marca de altura en la regleta
      var marca = nodo("div", "marca-alto");
      marca.style.bottom = pct(nv.altura_ref, H);
      marca.appendChild(nodo("span", null, String(nv.altura_ref)));
      marca.appendChild(nodo("b", null, nv.codigo));
      marca.title = nv.etiqueta + " · " + nv.altura_ref + " cm del piso";
      regleta.appendChild(marca);
    });

    // productos
    var porIdx = {};
    d.productos.forEach(function (p) { porIdx[p.idx] = p; });

    mod.niveles.forEach(function (nv) {
      nv.bloques.forEach(function (bl) {
        var prod = porIdx[bl.idx] || {};
        var grupo = nodo("div", "grupo-prod");
        grupo.dataset.idx = bl.idx;
        grupo.title = "#" + bl.numero + "  " + (prod.descripcion || "") +
                      "\n" + (prod.medidas || "") + " cm · " + bl.caras +
                      (bl.caras === 1 ? " cara" : " caras");

        bl.facings.forEach(function (f) {
          var c = nodo("div", "prod" + (prod.tiene_foto ? "" : " sin-foto"));
          c.style.left = pct(f.x, W);
          c.style.bottom = pct(f.y, H);
          c.style.width = pct(f.w, W);
          c.style.height = pct(f.h, H);
          if (prod.tiene_foto) {
            var img = new Image();
            img.src = urlImagen(bl.idx);
            img.alt = prod.descripcion || "";
            img.loading = "lazy";
            c.appendChild(img);
          }
          grupo.appendChild(c);
        });

        var num = nodo("div", "num", String(bl.numero));
        num.style.left = pct(bl.x + bl.ancho / 2, W);
        num.style.bottom = pct(bl.y + bl.alto, H);
        grupo.appendChild(num);

        grupo.onclick = function () { seleccionar(bl.idx, true); };
        mueble.appendChild(grupo);
      });
    });

    // cenefa al final, siempre por encima
    var cenefa = nodo("div", "cenefa");
    cenefa.style.height = pct(mu.cenefa, H);
    cenefa.appendChild(nodo("span", null, estado.categoria.toUpperCase()));
    mueble.appendChild(cenefa);

    plano.appendChild(regleta);
    plano.appendChild(mueble);
    caja.appendChild(plano);

    var ca = nodo("div", "cota-ancho");
    ca.appendChild(nodo("span", null, W + " cm"));
    caja.appendChild(ca);

    el.lienzo.appendChild(caja);
    requestAnimationFrame(aplicarZoom);
  }

  var altoPrevio = -1;

  function aplicarZoom() {
    var plano = el.lienzo.querySelector(".plano");
    if (!plano) return;
    altoPrevio = el.lienzo.clientHeight;
    // clientHeight incluye el padding del contenedor; abajo va la cota de ancho
    var disponible = altoPrevio - 36 - 24;
    if (estado.ajustar) estado.zoom = 1;
    plano.style.height = Math.max(240, disponible * estado.zoom) + "px";
    var mueble = plano.querySelector(".mueble");
    var cota = el.lienzo.querySelector(".cota-ancho");
    if (cota) cota.style.width = mueble ? mueble.getBoundingClientRect().width + "px" : "auto";
  }

  // el alto util recien se conoce cuando la grilla termina de acomodarse
  if (window.ResizeObserver) {
    new ResizeObserver(function () {
      if (el.lienzo.clientHeight !== altoPrevio) aplicarZoom();
    }).observe(el.lienzo);
  }

  /* -------------------------------------------------------------- detalle */
  var COLUMNAS = ["N°", "", "Producto", "Ubicación", "Caras"];

  function dibujarTabla() {
    var d = estado.datos;
    el.detalle.innerHTML = "";
    var tabla = nodo("table", "productos");
    var thead = nodo("thead"), tr = nodo("tr");
    COLUMNAS.forEach(function (c) { tr.appendChild(nodo("th", null, c)); });
    thead.appendChild(tr);
    tabla.appendChild(thead);

    var tbody = nodo("tbody");
    d.productos.forEach(function (p) {
      var fila = nodo("tr");
      fila.dataset.idx = p.idx;
      fila.dataset.busqueda = (p.numero + " " + p.descripcion + " " + p.barcode + " " +
                               p.material + " " + p.ubicacion).toLowerCase();

      var tdN = nodo("td", "col-n");
      tdN.appendChild(nodo("span", "pastilla", String(p.numero)));
      fila.appendChild(tdN);

      var tdImg = nodo("td", "col-img");
      if (p.tiene_foto) {
        var img = new Image();
        img.src = urlImagen(p.idx);
        img.alt = "";
        img.loading = "lazy";
        tdImg.appendChild(img);
      }
      fila.appendChild(tdImg);

      var tdP = nodo("td");
      tdP.appendChild(nodo("div", "desc", p.descripcion));
      var partes = [];
      if (p.barcode) partes.push(p.barcode);
      if (p.material) partes.push(p.material);
      partes.push(p.medidas + " cm");
      tdP.appendChild(nodo("div", "sub mono", partes.join("  ·  ")));
      fila.appendChild(tdP);

      var tdU = nodo("td");
      tdU.appendChild(nodo("div", "ubic",
        (d.modulos.length > 1 ? "M" + p.modulo + "-" : "") + p.ubicacion));
      tdU.appendChild(nodo("div", "sub", p.nivel));
      fila.appendChild(tdU);

      fila.appendChild(nodo("td", "mono", String(p.caras)));
      fila.onclick = function () { seleccionar(p.idx, false); };
      tbody.appendChild(fila);
    });
    tabla.appendChild(tbody);
    el.detalle.appendChild(tabla);
    filtrar();
  }

  function filtrar() {
    var q = el.buscador.value.trim().toLowerCase();
    el.detalle.querySelectorAll("tbody tr").forEach(function (tr) {
      tr.hidden = q && tr.dataset.busqueda.indexOf(q) === -1;
    });
  }

  /* ------------------------------------------------------------ selección */
  function seleccionar(idx, desdePlano) {
    var sel = estado.seleccion === idx ? null : idx;   // volver a tocar, deselecciona
    estado.seleccion = sel;

    // si el producto vive en otro modulo, hay que traerlo a pantalla primero
    if (sel !== null && !desdePlano) {
      var producto = estado.datos.productos.find(function (p) { return p.idx === sel; });
      if (producto && producto.modulo - 1 !== estado.modulo) {
        estado.modulo = producto.modulo - 1;
        dibujarTabs();
        dibujarPlano();
      }
    }
    marcar(desdePlano);
  }

  function marcar(desdePlano) {
    var sel = estado.seleccion;
    el.lienzo.querySelectorAll(".grupo-prod").forEach(function (g) {
      g.classList.toggle("activo", Number(g.dataset.idx) === sel);
    });
    var filaActiva = null;
    el.detalle.querySelectorAll("tbody tr").forEach(function (tr) {
      var esta = Number(tr.dataset.idx) === sel;
      tr.classList.toggle("activo", esta);
      if (esta) filaActiva = tr;
    });
    if (sel === null) return;

    if (desdePlano) {
      if (filaActiva) filaActiva.scrollIntoView({ block: "nearest", behavior: "smooth" });
    } else {
      var cara = el.lienzo.querySelector('.grupo-prod[data-idx="' + sel + '"] .prod');
      if (cara) cara.scrollIntoView({ block: "nearest", inline: "nearest", behavior: "smooth" });
    }
  }

  /* ------------------------------------------------------------------ PDF */
  function descargarPdf() {
    if (!estado.token) return;
    ocupado(true);
    pedir("/api/pdf", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(parametros())
    }).then(function (blob) {
      var url = URL.createObjectURL(blob);
      var a = document.createElement("a");
      a.href = url;
      a.download = "Planograma - " + (estado.categoria || "sin nombre") + ".pdf";
      document.body.appendChild(a);
      a.click();
      a.remove();
      setTimeout(function () { URL.revokeObjectURL(url); }, 4000);
      avisar("PDF descargado.");
    }).catch(function (e) {
      avisar(e.message, true);
    }).finally(function () { ocupado(false); });
  }

  /* -------------------------------------------------------------- eventos */
  el.archivo.addEventListener("change", function () {
    cargarArchivo(this.files[0]);
    this.value = "";
  });

  ["dragenter", "dragover"].forEach(function (ev) {
    el.drop.addEventListener(ev, function (e) {
      e.preventDefault();
      el.drop.classList.add("encima");
    });
  });
  ["dragleave", "drop"].forEach(function (ev) {
    el.drop.addEventListener(ev, function () { el.drop.classList.remove("encima"); });
  });
  el.drop.addEventListener("drop", function (e) {
    e.preventDefault();
    cargarArchivo(e.dataTransfer.files[0]);
  });
  window.addEventListener("dragover", function (e) { e.preventDefault(); });
  window.addEventListener("drop", function (e) { e.preventDefault(); });

  el.hoja.addEventListener("change", function () {
    estado.modulo = 0;
    generar();
  });
  el.categoria.addEventListener("input", function () {
    estado.categoria = this.value.trim() || el.hoja.value;
    var cenefa = el.lienzo.querySelector(".cenefa span");
    if (cenefa) cenefa.textContent = estado.categoria.toUpperCase();
  });
  [el.ancho, el.alto].forEach(function (i) {
    i.addEventListener("input", function () { estado.modulo = 0; generarPronto(); });
  });
  el.caras.addEventListener("input", function () {
    el.salidaCaras.textContent = this.value;
    generarPronto();
  });
  el.auto.addEventListener("change", function () {
    el.campoCaras.style.opacity = this.checked ? "1" : ".45";
    el.caras.disabled = !this.checked;
    generar();
  });
  el.buscador.addEventListener("input", filtrar);
  el.btnPdf.addEventListener("click", descargarPdf);

  $("#zoomMas").onclick = function () {
    estado.ajustar = false;
    estado.zoom = Math.min(4, estado.zoom * 1.25);
    aplicarZoom();
  };
  $("#zoomMenos").onclick = function () {
    estado.ajustar = false;
    estado.zoom = Math.max(0.4, estado.zoom / 1.25);
    aplicarZoom();
  };
  $("#zoomAjustar").onclick = function () {
    estado.ajustar = true;
    aplicarZoom();
  };

  window.addEventListener("resize", function () {
    clearTimeout(window._rz);
    window._rz = setTimeout(aplicarZoom, 120);
  });

  document.addEventListener("keydown", function (e) {
    if (e.key === "Escape" && estado.seleccion !== null) {
      seleccionar(estado.seleccion, false);
    }
  });
})();
