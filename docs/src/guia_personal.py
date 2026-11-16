"""PDF 2 — Guía personal completa: de los principios matemáticos al funcionamiento de la aplicación.
Documento de estudio y referencia para el autor. Todos los ejemplos numéricos se calculan con el motor.
"""
from __future__ import annotations

import cmath
import math
import sys

import figures as F
from common import (APP, AUTHOR, Doc, P, PageBreak, Spacer, box, bullets, cover_flowables, eq, numbered, table, toc,
                    version)
from rfwb.engine import antenna_em, matching as mt, reflection as rf, tline as tl
from rfwb.engine.impedance import analyze_circuit
from rfwb.engine.network import describe
from rfwb.engine.units import C0


def c(z, d=4):
    z = complex(z)
    return f"{z.real:.{d}g} {'+' if z.imag >= 0 else '−'} j{abs(z.imag):.{d}g}"


def H1(t):
    return P(t, "h1")


def H2(t):
    return P(t, "h2")


def H3(t):
    return P(t, "h3")


def part(title, intro, first=False):
    return ([] if first else [PageBreak()]) + [P(title, "h1"), P(intro), Spacer(1, 4)]


def build(out_path):
    doc = Doc(out_path, "Guía completa", "De los principios matemáticos al funcionamiento", "Guía personal")
    st = cover_flowables(
        "Guía completa de RF Engineering Workbench",
        "De los principios matemáticos al funcionamiento interno y el uso de cada módulo",
        f"Documento personal de estudio y referencia de {AUTHOR}. Explica, paso a paso, la matemática y la física en las que se basa "
        "cada cálculo de la aplicación, cómo está construida por dentro, cómo se usa cada módulo y cómo se mantiene y publica. "
        "Los ejemplos numéricos de esta guía se han calculado con el propio motor de la aplicación al generar el documento.")
    st += toc()
    st += [box("app", "Cómo leer esta guía", [
        "<b>Parte I</b> repasa la matemática imprescindible (números complejos, fasores, impedancia, decibelios). "
        "<b>Parte II</b> desarrolla la teoría de RF que implementa el motor: líneas, reflexión, carta de Smith, adaptación, parámetros S, "
        "estabilidad, modo mixto, TDR, calibración, antenas y microstrip. <b>Parte III</b> explica cómo está construida la aplicación. "
        "<b>Parte IV</b> es la guía de uso módulo a módulo y <b>Parte V</b> cubre el mantenimiento: compilar, probar, publicar y actualizar.",
        "Los cuadros verdes son <b>definiciones</b>; los azules, <b>ejemplos resueltos</b>; los amarillos, <b>advertencias</b>; y los grises indican "
        "<b>dónde aparece el concepto en la aplicación</b>."])]

    # ═════════════════════════ PARTE I ═════════════════════════
    st += part("Parte I — Fundamentos matemáticos", "Todo el análisis de circuitos de RF en régimen permanente se apoya en cuatro ideas: "
               "los números complejos, los fasores, la impedancia y la escala logarítmica. Esta parte las construye desde cero.", first=True)
    st += [H2("1. Números complejos"),
           P("Un número complejo z tiene una parte real y una parte imaginaria. En ingeniería eléctrica la unidad imaginaria se escribe "
             "<b>j</b> (no i, que se reserva para la corriente), con j² = −1."),
           eq(r"z = a + j\,b \qquad |z| = \sqrt{a^2+b^2} \qquad \varphi = \mathrm{atan2}(b,\,a)", label="1.1"),
           P("La misma cantidad puede escribirse en <b>forma polar</b> gracias a la fórmula de Euler, que une exponenciales y trigonometría:"),
           eq(r"e^{j\varphi} = \cos\varphi + j\,\sin\varphi \qquad\Rightarrow\qquad z = |z|\,e^{j\varphi} = |z|\,(\cos\varphi + j\,\sin\varphi)", label="1.2"),
           P("La forma rectangular es cómoda para sumar; la polar, para multiplicar y dividir (se multiplican módulos y se suman ángulos). "
             "El <b>conjugado</b> z* = a − jb refleja el número respecto al eje real; aparece en la potencia y en la adaptación conjugada."),
           box("ej", "Ejemplo", [f"z = 80 + j30: |z| = √(80² + 30²) = {abs(80 + 30j):.4f}, φ = atan2(30, 80) = {math.degrees(cmath.phase(80 + 30j)):.4f}°. "
                                 f"Su inverso es 1/z = z*/|z|² = {c(1 / (80 + 30j), 5)}."]),
           H2("2. Fasores y régimen senoidal permanente"),
           P("Una señal senoidal de frecuencia f se describe con su amplitud y su fase. El <b>fasor</b> V es el número complejo que guarda ambas; "
             "la señal real se recupera tomando la parte real:"),
           eq(r"v(t) = |V|\cos(\omega t + \varphi) = \mathrm{Re}\{V\,e^{j\omega t}\}, \qquad V = |V|e^{j\varphi},\qquad \omega = 2\pi f", label="2.1"),
           P("La gran ventaja es que derivar en el tiempo equivale a multiplicar por jω, de modo que las ecuaciones diferenciales de los "
             "circuitos se convierten en ecuaciones algebraicas con números complejos."),
           box("nota", "Convención de signo (muy importante)", [
               "La aplicación usa la convención <b>e<super>+jωt</super></b> (la habitual en ingeniería). Con ella la reactancia de una bobina es "
               "<b>positiva</b> y la de un condensador <b>negativa</b>. Algunos textos de física usan e<super>−jωt</super> y obtienen los signos "
               "opuestos: al comparar resultados, compruebe siempre la convención."]),
           H2("3. Impedancia y admitancia"),
           P("La <b>impedancia</b> es el cociente entre los fasores de tensión y corriente de un elemento: Z = V/I. Su parte real es la "
             "<b>resistencia</b> R (disipa potencia) y su parte imaginaria la <b>reactancia</b> X (almacena energía y la devuelve)."),
           eq(r"Z_R = R \qquad Z_L = j\omega L \qquad Z_C = \frac{1}{j\omega C} = -\,\frac{j}{\omega C}", label="3.1"),
           eq(r"X_L = \omega L > 0 \qquad\qquad X_C = -\frac{1}{\omega C} < 0", label="3.2"),
           P("La <b>admitancia</b> es su inversa, Y = 1/Z = G + jB (conductancia y susceptancia, en siemens). Las reglas de combinación son las de las resistencias, "
             "pero con números complejos:"),
           eq(r"Z_{serie} = Z_1 + Z_2 + \cdots \qquad\qquad Y_{paralelo} = Y_1 + Y_2 + \cdots", label="3.3"),
           ]
    rlc = analyze_circuit("RLC_series", 100e6, R=10, L=100e-9, C=25e-12)
    st += [box("ej", "Ejemplo resuelto (calculado por el motor): RLC serie a 100 MHz", [
        f"R = 10 Ω, L = 100 nH, C = 25 pF. ω = 2π·10⁸ = {rlc['omega']:.6g} rad/s.",
        f"X_L = ωL = {rlc['xl']:.5f} Ω;  X_C = −1/(ωC) = {rlc['xc']:.5f} Ω.",
        f"Z = R + j(X_L + X_C) = {c(rlc['z'], 6)} Ω  →  |Z| = {rlc['z_mag']:.5f} Ω, φ = {rlc['z_deg']:.4f}° (ligeramente capacitivo).",
        f"Y = 1/Z = {c(rlc['y'], 5)} S."]),
           H2("4. Potencia en corriente alterna"),
           P("Con fasores eficaces, la <b>potencia compleja</b> es S = V·I*. Su parte real es la potencia activa P (W, la que realmente se consume), "
             "la imaginaria la reactiva Q (var, energía que va y vuelve) y su módulo la aparente |S| (VA)."),
           eq(r"S = V\,I^{*} = P + jQ = |I|^2 Z \qquad\qquad \mathrm{FP} = \cos\varphi = P/|S|", label="4.1"),
           H2("5. Resonancia y factor de calidad Q"),
           P("En un circuito con L y C hay una frecuencia en la que sus reactancias se cancelan: la <b>resonancia</b>. En un RLC serie la impedancia "
             "se hace mínima (|Z| = R); en un RLC paralelo, máxima."),
           eq(r"f_0 = \frac{1}{2\pi\sqrt{LC}} \qquad Q_{serie} = \frac{1}{R}\sqrt{\frac{L}{C}} \qquad Q_{paralelo} = R\sqrt{\frac{C}{L}} \qquad BW_{-3\,dB} = \frac{f_0}{Q}", label="5.1"),
           P(f"Para el ejemplo anterior: f0 = {rlc['f0'] / 1e6:.4f} MHz, Q = {rlc['q_factor']:.4f} y BW = {rlc['bw_3db'] / 1e6:.4f} MHz. "
             "Un Q alto significa una resonancia estrecha y selectiva; en adaptación de impedancias, un Q alto implica poco ancho de banda."),
           F.rlc_response(),
           H2("6. Decibelios"),
           P("Las magnitudes de RF abarcan muchos órdenes de magnitud, por eso se usan escalas logarítmicas. Para cocientes de <b>potencia</b> se usa "
             "10·log10, y para cocientes de <b>amplitud</b> (tensión, corriente, |Γ|, |S|) se usa 20·log10, porque la potencia es proporcional al cuadrado de la amplitud."),
           eq(r"G_{dB} = 10\log_{10}\frac{P_2}{P_1} = 20\log_{10}\frac{|V_2|}{|V_1|} \qquad\qquad P_{dBm} = 10\log_{10}\frac{P}{1\,\mathrm{mW}}", label="6.1"),
           table([["+3 dB", "×2 en potencia"], ["+10 dB", "×10 en potencia"], ["+20 dB", "×100 en potencia, ×10 en amplitud"],
                  ["−3 dB", "mitad de potencia"], ["0 dBm", "1 mW"], ["30 dBm", "1 W"]], header=["Valor", "Significado"], widths=[40, 130]),
           ]

    # ═════════════════════════ PARTE II ═════════════════════════
    st += part("Parte II — Teoría de radiofrecuencia", "Cuando la longitud de un conductor deja de ser despreciable frente a la longitud de onda, "
               "las tensiones y corrientes varían a lo largo de él: aparecen las ondas, la reflexión y la necesidad de adaptar. Esta parte "
               "desarrolla la teoría exacta que implementa el motor.")
    lam145 = 0.66 * C0 / 145e6
    st += [H2("7. Líneas de transmisión"),
           P("Una línea (coaxial, microstrip, bifilar…) se modela con parámetros distribuidos por unidad de longitud: resistencia R′, inductancia L′, "
             "conductancia G′ y capacidad C′. Aplicando las leyes de Kirchhoff a un tramo infinitesimal se obtienen las <b>ecuaciones del telegrafista</b>:"),
           eq(r"\frac{dV}{dz} = -(R' + j\omega L')\,I \qquad\qquad \frac{dI}{dz} = -(G' + j\omega C')\,V", label="7.1"),
           P("Su solución es la suma de una onda que avanza (+) y otra que retrocede (−). De ella salen las dos magnitudes que caracterizan la línea: "
             "la <b>constante de propagación</b> γ y la <b>impedancia característica</b> Z0."),
           eq(r"V(z) = V^{+}e^{-\gamma z} + V^{-}e^{+\gamma z} \qquad \gamma = \alpha + j\beta = \sqrt{(R'+j\omega L')(G'+j\omega C')}", label="7.2"),
           eq(r"Z_0 = \sqrt{\frac{R' + j\omega L'}{G' + j\omega C'}} \qquad \beta = \frac{2\pi}{\lambda} \qquad \lambda = \frac{v_f\,c}{f}", label="7.3"),
           P("α (Np/m) es la atenuación y β (rad/m) la constante de fase. El <b>factor de velocidad</b> vf = 1/√εr indica qué fracción de la velocidad de la luz "
             f"lleva la onda (0.66 en un coaxial de polietileno sólido). Por ejemplo, a 145 MHz con vf = 0.66, λ = {lam145:.4f} m. "
             "La conversión de unidades de atenuación es α[Np/m] = α[dB/m]/8.686."),
           H3("Impedancia de entrada"),
           P("Si la línea de longitud ℓ termina en una carga ZL, la impedancia que se ve en su entrada es:"),
           eq(r"Z_{in} = Z_0\,\frac{Z_L + Z_0\tanh(\gamma\ell)}{Z_0 + Z_L\tanh(\gamma\ell)} \quad \rightarrow_{\alpha = 0} \quad Z_0\,\frac{Z_L + jZ_0\tan(\beta\ell)}{Z_0 + jZ_L\tan(\beta\ell)}", label="7.4"),
           table([["Cortocircuito (ZL = 0)", "Zin = jZ0·tan βℓ  (inductiva si ℓ < λ/4)"],
                  ["Circuito abierto (ZL = ∞)", "Zin = −jZ0·cot βℓ  (capacitiva si ℓ < λ/4)"],
                  ["ℓ = λ/2", "Zin = ZL  (la línea «desaparece»)"],
                  ["ℓ = λ/4", "Zin = Z0²/ZL  (inversor de impedancias)"],
                  ["Carga adaptada (ZL = Z0)", "Zin = Z0 para cualquier longitud"]], header=["Caso", "Resultado"], widths=[55, 115]),
           ]
    rline = tl.analyze_line(50, 145e6, 3.2, 0.66, 0.0, zl=100 + 50j)
    st += [H3("Onda estacionaria"),
           P("La superposición de onda incidente y reflejada produce máximos y mínimos de tensión fijos en el espacio, separados λ/4. "
             "Su cociente es la relación de onda estacionaria (VSWR) que se define en la sección siguiente."),
           F.standing_wave(),
           box("app", "En la aplicación", ["<b>Transmission Lines</b> calcula λ, β, α, θ = βℓ, Zin, Γ en carga y entrada, VSWR, el balance de potencias y dibuja la onda "
                                           "estacionaria, R(d) y X(d) y el recorrido de Γ en la carta. El deslizador «Posición sobre la línea» muestra Z(d) y Γ(d)."]),
           H2("8. Coeficiente de reflexión, VSWR y Return Loss"),
           P("En el punto donde una línea de impedancia Z0 se une a una carga Z, parte de la onda se refleja. El <b>coeficiente de reflexión</b> "
             "es el cociente (complejo) entre la onda reflejada y la incidente. Imponiendo V = Z·I en la carga se deduce:"),
           eq(r"\Gamma = \frac{V^{-}}{V^{+}} = \frac{Z - Z_0}{Z + Z_0} \qquad\Longleftrightarrow\qquad Z = Z_0\,\frac{1+\Gamma}{1-\Gamma}", label="8.1"),
           P("Para cargas pasivas |Γ| ≤ 1. Γ = 0 es adaptación perfecta; Γ = −1, cortocircuito; Γ = +1, circuito abierto. A partir de |Γ| se definen:"),
           eq(r"\mathrm{VSWR} = \frac{1+|\Gamma|}{1-|\Gamma|} \qquad RL = -20\log_{10}|\Gamma| \qquad ML = -10\log_{10}(1-|\Gamma|^2)", label="8.2"),
           eq(r"\frac{P_{refl}}{P_{inc}} = |\Gamma|^2 \qquad\qquad \frac{P_{entregada}}{P_{inc}} = 1 - |\Gamma|^2", label="8.3"),
           ]
    rows = []
    for s in (1.1, 1.2, 1.5, 2.0, 3.0, 5.0):
        g = rf.gamma_from_vswr(s)
        rows.append([f"{s:g} : 1", f"{g:.4f}", f"{rf.return_loss_db(g):.2f} dB", f"{100 * g * g:.2f} %", f"{rf.mismatch_loss_db(g):.3f} dB"])
    m = rf.reflection_metrics(80 + 30j, 50)
    st += [table(rows, header=["VSWR", "|Γ|", "Return Loss", "Potencia reflejada", "Mismatch loss"], widths=[30, 30, 35, 40, 35]),
           Spacer(1, 4),
           box("ej", "Ejemplo resuelto: Z = 80 + j30 Ω sobre Z0 = 50 Ω", [
               f"Γ = (30 + j30)/(130 + j30) = {c(m['gamma'], 6)} = {m['gamma_mag']:.5f}∠{m['gamma_deg']:.3f}°",
               f"VSWR = (1 + {m['gamma_mag']:.5f})/(1 − {m['gamma_mag']:.5f}) = {m['vswr']:.4f};  RL = {m['return_loss_db']:.4f} dB;  "
               f"se refleja el {m['reflected_pct']:.3f} % de la potencia."]),
           box("nota", "Return Loss positivo frente a |S11| negativo", ["La aplicación usa RL como número positivo (−20·log|Γ|). |S11| en dB es su opuesto: "
                                                                       "RL = 15 dB equivale a |S11| = −15 dB. Ambos describen lo mismo."]),
           H2("9. La carta de Smith"),
           P("La carta de Smith es el plano complejo de Γ con una rejilla dibujada encima que permite leer directamente la impedancia "
             "normalizada z = Z/Z0 = r + jx. Se obtiene de la transformación (8.1), que es <b>bilineal</b>: lleva rectas y círculos del plano z "
             "a círculos en el plano Γ."),
           eq(r"\Gamma = \frac{z - 1}{z + 1} \qquad z = \frac{1+\Gamma}{1-\Gamma}, \qquad z = r + jx", label="9.1"),
           P("Separando partes real e imaginaria (Γ = u + jv) se demuestra que las curvas de r constante y de x constante son circunferencias:"),
           eq(r"\left(u - \frac{r}{1+r}\right)^2 + v^2 = \left(\frac{1}{1+r}\right)^2 \qquad (u-1)^2 + \left(v - \frac{1}{x}\right)^2 = \left(\frac{1}{x}\right)^2", label="9.2"),
           P("Son exactamente las fórmulas con las que la aplicación dibuja la rejilla (archivo frontend/src/lib/smith.ts). Lectura básica:"),
           *bullets(["El <b>centro</b> es z = 1 (adaptación); el <b>borde</b>, |Γ| = 1.",
                     "El <b>extremo izquierdo</b> es el cortocircuito; el <b>derecho</b>, el circuito abierto.",
                     "La mitad <b>superior</b> es inductiva (x > 0); la <b>inferior</b>, capacitiva (x < 0).",
                     "Un círculo centrado en el origen une puntos de igual |Γ|, es decir, de igual VSWR.",
                     "La carta de <b>admitancias</b> es la misma rejilla girada 180°: y = 1/z corresponde a −Γ."]),
           F.smith_regions(),
           H3("Desplazarse por una línea"),
           P("Alejarse una distancia d de la carga en una línea sin pérdidas multiplica Γ por e<super>−j2βd</super>: el punto <b>gira</b> en sentido horario "
             "alrededor del centro, sin cambiar |Γ|. Una vuelta completa corresponde a <b>λ/2</b>; por eso el borde de la carta lleva la escala "
             "«longitudes de onda hacia el generador» (0 a 0.5)."),
           eq(r"\Gamma(d) = \Gamma_L\,e^{-2\gamma d} \quad \rightarrow_{\alpha = 0} \quad |\Gamma(d)| = |\Gamma_L|,\quad \angle\Gamma(d) = \angle\Gamma_L - 2\beta d", label="9.3"),
           F.smith_example(width=88),
           box("app", "En la aplicación", ["<b>Smith Chart</b>: introduzca Z (80+j30, 25-j10, 100∠45…), haga clic o arrastre el punto, active la rejilla de admitancia, "
                                           "el círculo de VSWR y el desplazamiento por línea. La lectura del cursor muestra Γ, z, Z, VSWR y la escala λ. "
                                           "El botón de descarga exporta la carta en SVG o PNG de 4000 px."]),
           ]
    res = mt.design("L", 25 - 40j, 50 + 0j, 433e6, vswr_target=2.0)
    s0 = res["solutions"][0]
    st += [H2("10. Adaptación de impedancias"),
           P("Una fuente de impedancia Zs entrega la máxima potencia cuando la carga que ve es su conjugada (Zin = Zs*). Si Zs es real (50 Ω), "
             "esto equivale a Γ = 0. Una <b>red de adaptación</b> sin pérdidas, colocada entre fuente y carga, transforma ZL en Zs*."),
           eq(r"Z_{in} = Z_s^{*} \qquad \Gamma_p = \frac{Z_L - Z_s^{*}}{Z_L + Z_s} \quad (\mathrm{coeficiente\ de\ onda\ de\ potencia})", label="10.1"),
           H3("Red L"),
           P("Dos elementos reactivos: uno en paralelo y otro en serie. Si el elemento en paralelo está junto a la carga, su susceptancia B debe llevar "
             "la parte real de la admitancia transformada al valor buscado; después la reactancia serie cancela lo que sobra:"),
           eq(r"\mathrm{Re}\left\{\frac{1}{G_L + j(B_L + B)}\right\} = R_t \;\Rightarrow\; (B_L + B)^2 = \frac{G_L}{R_t} - G_L^2", label="10.2"),
           P("Cada raíz cuadrada da dos signos y hay dos topologías, por lo que existen hasta cuatro soluciones. La aplicación las calcula todas "
             "y <b>verifica numéricamente</b> cada una antes de mostrarla. Una reactancia positiva es una bobina (L = X/ω) y una negativa un condensador "
             "(C = −1/(ωX)); para susceptancias, al revés."),
           H3("Redes Pi y T"),
           P("Una red L tiene un Q fijado por la relación de resistencias, Q = √(R_max/R_min − 1). Para elegir el Q (y por tanto el ancho de banda) se encadenan dos redes L "
             "a través de una resistencia virtual Rv: Rv = R_max/(1 + Q²) en la Pi y Rv = R_min(1 + Q²) en la T."),
           H3("Transformador de cuarto de onda y stubs"),
           eq(r"Z_1 = \sqrt{R_s\,R} \qquad Y_{stub\ abierto} = jY_0\tan\beta\ell \qquad Y_{stub\ corto} = -jY_0\cot\beta\ell", label="10.3"),
           P("El transformador λ/4 sólo adapta cargas reales; si ZL es compleja, se añade antes un tramo de línea hasta un máximo o mínimo de tensión, donde la impedancia "
             "es real. En el <b>stub simple</b> se busca la distancia d a la que Re{Y(d)} = 1/Rs y se cancela la susceptancia restante con un stub. El <b>doble stub</b> "
             "fija las posiciones y ajusta las longitudes, pero existe una región de cargas que no puede adaptar con una separación dada."),
           H3("La adaptación es de banda estrecha: límite de Bode–Fano"),
           P("Los elementos reactivos dependen de la frecuencia, así que la adaptación sólo es perfecta en f0. Bode y Fano demostraron que, para una carga con "
             "almacenamiento de energía (factor Q_L = |X_L|/R_L), ninguna red sin pérdidas puede mantener |Γ| ≤ Γm en más ancho de banda que:"),
           eq(r"\frac{\Delta f}{f_0} \leq \frac{\pi}{Q_L\,\ln(1/\Gamma_m)}", label="10.4"),
           F.matching_example(),
           box("ej", "Ejemplo calculado por el motor (ZL = 25 − j40 Ω, Zs = 50 Ω, 433 MHz)", [
               f"Desadaptación inicial: |Γ| = {abs(res['gamma_before']):.4f}, VSWR = {res['vswr_before']:.4f}.",
               f"Solución 1: {', '.join(describe(e) for e in s0['elements'])}.",
               f"Ancho de banda con VSWR ≤ 2: {s0['bandwidth']['fractional'] * 100:.2f} % · límite de Bode–Fano: {res['bode_fano']['max_fractional_bw'] * 100:.1f} %."]),
           box("app", "En la aplicación", ["<b>Matching Designer</b> ofrece L, Pi, T, λ/4, stub simple y doble; valores normalizados E12/E24 o de la biblioteca, Q finito de los "
                                           "componentes (ganancia de transductor G_T) y análisis Monte Carlo de tolerancias. <b>Circuit Builder</b> permite construir la red a mano y ver "
                                           "cada tramo de la trayectoria en la carta."]),
           ]
    st += [H2("11. Parámetros S"),
           P("A alta frecuencia no es práctico medir tensiones y corrientes en circuito abierto o cortocircuito, pero sí ondas. En cada puerto se definen "
             "ondas de potencia incidente (a) y reflejada (b), normalizadas a la impedancia de referencia Z0:"),
           eq(r"a = \frac{V + Z_0 I}{2\sqrt{Z_0}} \qquad b = \frac{V - Z_0 I}{2\sqrt{Z_0}} \qquad b_i = \sum_j S_{ij}\,a_j", label="11.1"),
           *bullets(["<b>S11</b>: reflexión en el puerto 1 con el puerto 2 terminado en Z0 (es el Γ de entrada).",
                     "<b>S21</b>: transmisión del puerto 1 al 2 (|S21| en dB negativo = pérdida de inserción; positivo = ganancia).",
                     "Una red <b>recíproca</b> cumple S12 = S21; una red <b>sin pérdidas</b> tiene una matriz S unitaria.",
                     "Los parámetros S dependen de Z0: cambiar la referencia cambia los valores."]),
           eq(r"Z = Z_0\,(I+S)(I-S)^{-1} \qquad \Gamma_{in} = S_{11} + \frac{S_{12}S_{21}\Gamma_L}{1 - S_{22}\Gamma_L} \qquad \tau_g = -\frac{d\varphi}{d\omega}", label="11.2"),
           P("Para encadenar bloques se usa la matriz <b>ABCD</b>, que se multiplica en cascada; el motor representa así líneas, elementos serie, en paralelo y stubs, y la convierte a S cuando hace falta."),
           box("nota", "Trabajar siempre con números complejos", ["Las magnitudes en dB se derivan de los datos complejos, nunca al revés: sin fase no se puede convertir S a impedancia, "
                                                                 "calcular Γin con otra carga, ni aplicar una calibración."]),
           H2("12. Estabilidad y ganancia de dispositivos activos"),
           P("Un transistor puede oscilar si alguna impedancia de fuente o de carga pasiva hace |Γin| > 1 o |Γout| > 1. El criterio de Rollett y el de Edwards–Sinsky lo resumen:"),
           eq(r"\Delta = S_{11}S_{22} - S_{12}S_{21} \qquad K = \frac{1 - |S_{11}|^2 - |S_{22}|^2 + |\Delta|^2}{2|S_{12}S_{21}|} \qquad \mu = \frac{1-|S_{11}|^2}{|S_{22}-\Delta S_{11}^{*}| + |S_{12}S_{21}|}", label="12.1"),
           P("El dispositivo es <b>incondicionalmente estable</b> si μ > 1 (equivalente a K > 1 y |Δ| < 1). Si no lo es, los <b>círculos de estabilidad</b> delimitan las "
             "cargas peligrosas en la carta. Cuando K > 1 existe la máxima ganancia disponible MAG = |S21/S12|·(K − √(K² − 1)); los <b>círculos de ganancia</b> "
             "muestran qué ΓL (o ΓS) dan una ganancia determinada."),
           H2("13. Parámetros en modo mixto"),
           P("En líneas diferenciales (USB, Ethernet, LVDS…) interesa la respuesta a la señal diferencial y a la común. Para cada par de puertos (p, n):"),
           eq(r"a_d = \frac{a_p - a_n}{\sqrt{2}} \qquad a_c = \frac{a_p + a_n}{\sqrt{2}} \qquad S_{mm} = M\,S\,M^{T}", label="13.1"),
           P("Sdd describe el comportamiento diferencial, Scc el común, y Sdc/Scd la <b>conversión de modo</b>, que en un par perfectamente simétrico es cero. "
             "Las referencias resultantes son 2·Z0 (diferencial) y Z0/2 (común). La aplicación usa pares consecutivos (1-2, 3-4), la convención de scikit-rf."),
           H2("14. Dominio del tiempo (TDR)"),
           P("La respuesta en frecuencia S11(f) y la respuesta temporal están unidas por la transformada de Fourier. Aplicando la transformada inversa a S11 "
             "se obtiene una «reflectometría» que localiza discontinuidades a lo largo de un cable:"),
           eq(r"h(t) = \mathcal{F}^{-1}\{S_{11}(f)\,W(f)\} \qquad \rho(t) = \int h\,dt \qquad Z(t) = Z_0\,\frac{1+\rho}{1-\rho} \qquad d = \frac{v_f\,c\,t}{2}", label="14.1"),
           *bullets(["<b>Low-pass</b>: requiere frecuencias armónicas (f_n = n·Δf) y extrapolar DC; da la respuesta al escalón y, con ella, Z(t).",
                     "<b>Band-pass</b>: vale para cualquier rejilla, pero sólo da la magnitud del impulso (localización).",
                     "La <b>ventana</b> W (Kaiser, Hann) reduce las oscilaciones a costa de resolución. Resolución ≈ vf·c/(2·span); alcance ≈ vf·c/(2Δf)."]),
           F.tdr_example(),
           H2("15. Calibración del VNA"),
           P("Cables, conectores y acopladores añaden errores sistemáticos. En un puerto se modelan con tres términos: directividad e00, desadaptación de fuente e11 "
             "y seguimiento de reflexión e10e01:"),
           eq(r"\Gamma_m = e_{00} + \frac{e_{10}e_{01}\,\Gamma_a}{1 - e_{11}\Gamma_a} \quad\Rightarrow\quad \Gamma_m = e_{00} + \Gamma_a\Gamma_m\,e_{11} - \Gamma_a\,\Delta_e", label="15.1"),
           P("La segunda forma es lineal en (e00, e11, Δe): midiendo tres estándares conocidos (Open, Short, Load) se resuelve un sistema 3×3 en cada frecuencia, "
             "y después se despeja el Γ real del dispositivo. En dos puertos el modelo completo tiene <b>12 términos</b> (SOLT). Si los estándares no son ideales, se describen con "
             "una línea de offset (retardo, pérdidas, Z0) y polinomios C(f) = C0 + C1f + C2f² + C3f³ (Open) y L(f) (Short) tomados de la documentación del kit."),
           ]
    d2 = antenna_em.wire_antenna("dipole", C0, 0.5, 1e-5)
    st += [H2("16. Antenas"),
           P("Una antena se comporta, desde su puerto, como una impedancia: el S11 dice cuánta potencia se <b>refleja</b>, no cuánta se <b>radia</b>. "
             "Una resistencia de 50 Ω tiene un S11 perfecto y no radia nada. Por eso la ganancia y el diagrama necesitan medidas de campo o un modelo electromagnético."),
           H3("Modelo analítico del dipolo delgado"),
           P("Con un hilo delgado alimentado en el centro, la corriente es aproximadamente sinusoidal. Integrando el campo lejano se obtiene el diagrama F(θ) "
             "y, a partir de él, la resistencia de radiación y la directividad:"),
           eq(r"I(z) = I_0\sin\left(k\left(\frac{L}{2} - |z|\right)\right) \qquad F(\theta) = \frac{\cos\left(\frac{kL}{2}\cos\theta\right) - \cos\frac{kL}{2}}{\sin\theta}", label="16.1"),
           eq(r"R_r = \frac{\eta}{2\pi}\int_0^{\pi} F(\theta)^2\sin\theta\,d\theta \qquad D = \frac{2\,F_{max}^2}{\int_0^{\pi} F^2\sin\theta\,d\theta} \qquad Z_{in} = \frac{Z_m}{\sin^2(kL/2)}", label="16.2"),
           eq(r"R_s = \sqrt{\frac{\omega\mu_0}{2\sigma}} \qquad R_L = \frac{R_s}{2\pi a}\int |I(z)/I_0|^2 dz \qquad e = \frac{R_r}{R_r + R_L} \qquad G = e\,D", label="16.3"),
           P(f"Para el dipolo de media onda el motor obtiene Z = {c(d2['z_in'], 5)} Ω (reactancia por el método de la FEM inducida) y D = {d2['directivity']:.4f} "
             f"({d2['directivity_dbi']:.3f} dBi), los valores clásicos de Balanis. Un monopolo sobre plano de masa perfecto equivale, por teoría de imágenes, a medio dipolo: "
             "mitad de impedancia y doble directividad."),
           F.dipole_pattern(),
           P("Desde el puerto, el factor Q de la antena (Yaghjian–Best) se estima de la derivada de su impedancia y limita el ancho de banda: FBW ≈ (s − 1)/(Q·√s) para VSWR ≤ s."),
           H2("17. Microstrip y coaxial"),
           eq(r"Z_{0,coax} = \frac{60}{\sqrt{\varepsilon_r}}\ln\frac{D}{d} \qquad v_f = \frac{1}{\sqrt{\varepsilon_{eff}}} \qquad \alpha(f) \approx \alpha(f_{ref})\sqrt{f/f_{ref}}", label="17.1"),
           P("En microstrip parte del campo va por el aire, así que se usa una permitividad efectiva εeff entre 1 y εr. El modelo de Hammerstad–Jensen "
             "la calcula a partir de W/h y εr; la versión completa (vía scikit-rf) añade el espesor del cobre, la <b>dispersión</b> de Kirschning–Jansen "
             "(εeff crece con la frecuencia) y las pérdidas de conductor (efecto pelicular y rugosidad) y del dieléctrico (tan δ). La atenuación de los cables "
             "se escala con √f porque domina la pérdida en los conductores."),
           ]

    # ═════════════════════════ PARTE III ═════════════════════════
    st += part("Parte III — Cómo está construida la aplicación", "La regla de oro del diseño es que cada fórmula exista en un único sitio: el motor. "
               "Todo lo demás (API, interfaz, informes) sólo transporta y presenta sus resultados.")
    st += [F.architecture(),
           H2("18. Recorrido de un cálculo"),
           *numbered(["Usted escribe «80+j30» en la interfaz (React). El módulo envía una petición HTTP local, por ejemplo POST /api/rf/reflection.",
                      "La API (FastAPI) valida la entrada y la convierte: parse_complex interpreta 80+j30, 100∠45, j25…; parse_quantity entiende prefijos (10n, 2.4G).",
                      "El motor calcula con números complejos de NumPy y, a la vez, rellena una <b>traza</b> con fórmula, sustitución, resultado e interpretación.",
                      "La respuesta se serializa a JSON: los complejos como {re, im} y el infinito como «inf» (JSON no admite infinitos).",
                      "La interfaz presenta los valores; si el modo educativo está activo, muestra también la traza paso a paso."]),
           H2("19. El motor por dentro"),
           table([["units.py", "Unidades, prefijos SI, validación de entradas, parseo de complejos."],
                  ["reflection.py", "Γ, VSWR, RL, mismatch loss, potencia reflejada; onda de potencia."],
                  ["impedance.py", "Reactancias, circuitos RLC, redes por expresión, modelos reales de L/C/R."],
                  ["network.py", "Cascadas ABCD de elementos, líneas y stubs; Zin; trayectorias en la carta."],
                  ["tline.py", "Propagación, Zin, perfiles, geometrías (coaxial, bifilar, microstrip con scikit-rf)."],
                  ["matching.py", "Redes L, Pi, T, λ/4, stub simple/doble, Bode–Fano, valores normalizados."],
                  ["sparams.py · stability.py · mixedmode.py", "Conversiones S/Z/Y/ABCD/H/G, métricas, bandas, K/μ, círculos, modo mixto."],
                  ["tdr.py · calibration.py · calkit.py", "Dominio del tiempo; SOL propio y SOLT (scikit-rf); modelos de kits."],
                  ["antenna.py · antenna_em.py", "Análisis de puerto de antenas; modelo EM analítico de dipolo/monopolo."],
                  ["tolerance.py · selftest.py", "Monte Carlo de tolerancias; autoverificación ejecutable desde el Dashboard."]],
                 header=["Archivo (backend/rfwb/engine)", "Contenido"], widths=[62, 108]),
           H2("20. Procedencia de los datos"),
           P("Cada conjunto de datos se guarda en SQLite con un origen obligatorio que nunca cambia: <b>imported</b> (Touchstone), <b>simulated</b> (modelos), "
             "<b>measured</b> (VNA conectado) o <b>derived</b> (procesado, p. ej. calibración, que además guarda de qué datos procede). La interfaz y los informes "
             "muestran ese origen con colores distintos."),
           H2("21. Escritorio, instalador y actualizaciones"),
           P("Electron abre la ventana y arranca el motor como un subproceso en un puerto libre asignado por el sistema; al cerrar la ventana, lo detiene. "
             "En la versión instalada el motor es un ejecutable autónomo creado con PyInstaller, de modo que no hace falta Python. "
             "Al arrancar, electron-updater consulta las Releases públicas de GitHub y, si hay una versión nueva, pregunta antes de descargarla e instalarla."),
           H2("22. Cómo se garantiza la precisión"),
           P("La batería de pruebas (backend/tests) compara el motor con: resultados analíticos (cargas resistivas, abierto, corto, λ/4, λ/2), ejemplos resueltos de Pozar "
             "(5.1, 5.2, 5.4) y Balanis (dipolo, monopolo), y con scikit-rf (conversiones, estabilidad, Touchstone, calibración, modo mixto, líneas con pérdidas). "
             "El script de publicación no publica si una sola prueba falla."),
           ]

    # ═════════════════════════ PARTE IV ═════════════════════════
    st += part("Parte IV — Guía de uso, módulo a módulo", "Recomendaciones prácticas para sacar partido a cada módulo. Todas las entradas aceptan prefijos SI "
               "(10n = 10 nH, 4.7p, 433MHz, 2.4G) y las impedancias se escriben como 80+j30, 25-j10, 100∠45 o j50.")
    guide = [
        ("Dashboard", ["Pulse «Ejecutar» en Validación del motor para comprobar que todo calcula bien (10 casos de referencia).",
                       "«Buscar actualizaciones» consulta GitHub y muestra la versión instalada.",
                       "Con el modo educativo activo aparecen los conceptos fundamentales."]),
        ("Smith Chart", ["Escriba la impedancia y la Z0 de referencia; añada hasta 8 puntos para compararlos.",
                         "Haga clic en la carta para situar el punto seleccionado o arrástrelo; rueda = zoom, doble clic = vista completa.",
                         "Con la frecuencia indicada, obtendrá el equivalente serie y paralelo (L o C).",
                         "El deslizador de línea muestra cómo gira el punto hacia el generador o la carga."]),
        ("Circuit Builder", ["Defina ZL, Z0 y f0, o cargue un ejemplo. El circuito se lee siempre ZL → 1 → 2 → … → Zin.",
                             "Pulse un «+» del esquema (o «Insertar aquí») para elegir dónde irá el siguiente elemento; después pulse el tipo.",
                             "Cada L/C/R tiene un deslizador de ÷10 a ×10; cada línea o stub, uno de longitud de 0 a 0.5 λ.",
                             "Seleccione un elemento (en la lista o en el esquema) para resaltarlo; bórrelo con «Eliminar» o la tecla Supr."]),
        ("Impedance Analyzer", ["Elija la topología (RL, RC, LC, RLC serie o paralelo) o escriba una red como R(50) + (L(10n) || C(4.7p)).",
                                "Obtendrá Z, Y, potencias con fuente de 1 V eficaz, resonancia, Q, BW y el barrido |Z|, fase, R y X."]),
        ("Matching Designer", ["Introduzca ZL, Zs, f0 y el método. Revise todas las soluciones: cada una tiene su esquema, ancho de banda y G_T.",
                               "«Valores normalizados» ajusta a E12/E24 o a la biblioteca y muestra cuánto empeora el VSWR.",
                               "Ponga un Q finito a los componentes para ver la pérdida real, y use Monte Carlo para ver el efecto de las tolerancias.",
                               "Compare siempre el ancho de banda obtenido con el límite de Bode–Fano."]),
        ("Transmission Lines", ["Elija el tipo de línea: genérica, coaxial por geometría, microstrip (con espesor, tan δ y pérdidas), bifilar o un cable de la biblioteca.",
                                "La atenuación puede darse a una frecuencia de referencia: se escala con √f.",
                                "Use la terminación (abierto, corto, adaptada o ZL) y el deslizador de posición para estudiar Γ(d) y Z(d)."]),
        ("S-Parameters", ["Seleccione un conjunto de datos o genere uno simulado (cascada de elementos o expresión a masa).",
                          "Haga clic en una gráfica para poner el marcador; verá |S|, fase, Z, VSWR, RL o IL en ese punto.",
                          "Pestañas: Magnitud, Fase, Smith, VSWR, RL, retardo de grupo, Estabilidad (2 puertos), TDR y Modo mixto (4 puertos)."]),
        ("Antenna Analyzer", ["Fuentes: modelo RLC equivalente, datos importados/medidos, tabla f-R-X o «Modelo EM (hilo)» para dipolos y monopolos.",
                              "Obtendrá la resonancia, el ancho de banda con el VSWR elegido y Q; con el modelo EM, además, diagrama, D, eficiencia y ganancia.",
                              "«Fijar actual» permite superponer varios diseños o medidas."]),
        ("Component Library", ["Añada componentes reales con los datos de su hoja de características (Q, ESR, SRF). La gráfica |Z(f)| muestra la autorresonancia.",
                               "Para cables, indique Z0, factor de velocidad y la atenuación con su frecuencia."]),
        ("Touchstone Importer", ["Arrastre uno o varios archivos .s1p–.s4p. Revise los metadatos, los avisos y el contraste con scikit-rf antes de guardar.",
                                 "Desde la tabla puede abrir el conjunto en S-Parameters o exportarlo en RI/MA/DB o CSV."]),
        ("VNA Integration", ["«Buscar» detecta puertos serie, LibreVNA-GUI y recursos VISA. Sin instrumento la aplicación lo indica y no inventa datos.",
                             "Con un VNA: configure el barrido, capture o use el barrido continuo y guarde la captura que interese.",
                             "Calibre con SOL (1 puerto) o SOLT (2 puertos), con estándares ideales o con los coeficientes de su kit."]),
        ("Reports", ["En cualquier módulo pulse «Añadir al informe». Aquí ordene, revise y exporte a PDF o CSV.",
                     "Cada elemento indica si es cálculo, simulación, archivo importado o medición."]),
    ]
    for name, items in guide:
        st += [H2(name), *bullets(items)]
    st += [box("app", "Atajos útiles", ["Tema claro/oscuro y color de acento: botón «Tema». Proyecto: guarda las entradas de todos los módulos y el informe. "
                                        "Modo educativo: muestra u oculta las explicaciones y los desarrollos paso a paso."])]

    # ═════════════════════════ PARTE V ═════════════════════════
    st += part("Parte V — Mantenimiento y publicación", "Cómo trabajar con el código: ejecutar en desarrollo, probar, compilar y publicar versiones.")
    st += [H2("23. Estructura del proyecto"),
           table([["backend/rfwb/engine", "Motor matemático (Python)"], ["backend/rfwb/api", "Endpoints FastAPI"],
                  ["backend/rfwb/io · vna · reports · library", "Touchstone, drivers VNA, informes, biblioteca"],
                  ["backend/tests", "Batería de validación (pytest)"], ["frontend/src", "Interfaz React (módulos, componentes, temas)"],
                  ["electron", "Proceso principal, actualizaciones, preload"], ["scripts", "build_engine, smoke_engine, release"],
                  ["docs", "Documentación y generadores de PDF"]], header=["Carpeta", "Contenido"], widths=[70, 100]),
           H2("24. Comandos"),
           table([["npm run dev", "Desarrollo con recarga en caliente (Vite + Electron)."],
                  ["npm run test:engine", "Ejecuta todas las pruebas del motor."],
                  ["npm start", "Compila la interfaz y abre la aplicación."],
                  ["npm run build:engine", "Compila el motor con PyInstaller y lo prueba (prueba de humo)."],
                  ["npm run dist", "Genera el instalador sin publicarlo."],
                  ["npm run release", "Pruebas + compilación + publicación en GitHub + etiqueta de versión."]], header=["Comando", "Qué hace"], widths=[48, 122], font="cell"),
           H2("25. Publicar una versión"),
           *numbered(["Suba la versión: npm version patch --no-git-tag-version (minor para funciones nuevas).",
                      "Confirme los cambios: git commit -am \"Versión X.Y.Z\".",
                      "Publique: npm run release. Si algo falla (pruebas, compilación, subida), no se publica nada.",
                      "La aplicación instalada detectará la versión nueva en el siguiente arranque."]),
           H2("26. Dónde están sus datos"),
           P("La base de datos de la aplicación instalada está en %APPDATA%\\rf-engineering-workbench\\data\\workbench.sqlite3 (biblioteca, conjuntos de datos y proyectos). "
             "Para hacer una copia de seguridad basta con copiar ese archivo con la aplicación cerrada. El registro de actualizaciones está en updater.log, en la misma carpeta superior.", "box"),
           H2("27. Problemas conocidos y soluciones"),
           table([["Electron no se instala bien (Node 26)", "Extraer a mano el zip oficial en caché y crear path.txt (ver README)."],
                  ["«Cannot create symbolic link» al compilar", "Extraer winCodeSign en la caché sin los dos enlaces de macOS, o activar el Modo de desarrollador."],
                  ["Puerto 8765 ocupado", "Otra aplicación del equipo lo usa; por eso la app usa un puerto libre aleatorio."],
                  ["Windows muestra «Editor desconocido»", "El instalador no está firmado: «Más información → Ejecutar de todas formas»."]],
                 header=["Síntoma", "Solución"], widths=[62, 108]),
           ]

    # ═════════════════════════ APÉNDICES ═════════════════════════
    st += [PageBreak(), H1("Apéndice A — Resumen de fórmulas"),
           table([["Reactancias", "X_L = ωL ; X_C = −1/(ωC)"], ["Reflexión", "Γ = (Z − Z0)/(Z + Z0) ; Z = Z0(1 + Γ)/(1 − Γ)"],
                  ["VSWR / RL", "VSWR = (1 + |Γ|)/(1 − |Γ|) ; RL = −20·log|Γ|"], ["Línea", "Zin = Z0(ZL + Z0·tanh γℓ)/(Z0 + ZL·tanh γℓ)"],
                  ["λ/4", "Zin = Z0²/ZL"], ["Resonancia", "f0 = 1/(2π√(LC)) ; BW = f0/Q"], ["S ↔ Z", "Z = Z0(I + S)(I − S)⁻¹"],
                  ["Γin", "Γin = S11 + S12·S21·ΓL/(1 − S22·ΓL)"], ["Estabilidad", "μ > 1 ⇔ incondicionalmente estable"],
                  ["Bode–Fano", "Δf/f0 ≤ π/(Q_L·ln(1/Γm))"], ["Dipolo λ/2", "Z ≈ 73 + j42.5 Ω ; D = 1.64 (2.15 dBi)"]], header=["Concepto", "Fórmula"], widths=[38, 132]),
           H1("Apéndice B — Glosario"),
           table([["ABCD", "Matriz de transmisión; se multiplica al encadenar bloques."], ["Admitancia", "Y = 1/Z = G + jB (S)."],
                  ["Bode–Fano", "Límite teórico del ancho de banda de adaptación."], ["Conjugado", "z* = a − jb."],
                  ["dBi", "Ganancia respecto a una antena isótropa."], ["Return Loss", "Atenuación de la onda reflejada (dB, positivo)."],
                  ["SOLT", "Calibración Short-Open-Load-Thru de dos puertos (12 términos)."], ["SRF", "Frecuencia de autorresonancia de un componente."],
                  ["Stub", "Tramo de línea abierto o en corto usado como reactancia."], ["Touchstone", "Formato estándar de archivos de parámetros de red."],
                  ["VNA", "Analizador vectorial de redes."], ["VSWR / ROE", "Relación de onda estacionaria."]], header=["Término", "Significado"], widths=[38, 132]),
           H1("Apéndice C — Bibliografía"),
           *bullets(["D. M. Pozar, <i>Microwave Engineering</i>, 4.ª ed., Wiley, 2012 (líneas, adaptación, parámetros S, estabilidad).",
                     "C. A. Balanis, <i>Antenna Theory: Analysis and Design</i>, 4.ª ed., Wiley, 2016 (dipolos, FEM inducida).",
                     "E. Hammerstad y Ø. Jensen, «Accurate models for microstrip computer-aided design», IEEE MTT-S, 1980.",
                     "M. Kirschning y R. H. Jansen, «Accurate model for effective dielectric constant of microstrip», Electronics Letters, 1982.",
                     "M. L. Edwards y J. H. Sinsky, «A new criterion for linear 2-port stability using geometrically derived parameters», IEEE T-MTT, 1992.",
                     "K. Kurokawa, «Power waves and the scattering matrix», IEEE T-MTT, 1965.",
                     "D. A. Frickey, «Conversions between S, Z, Y, h, ABCD and T parameters», IEEE T-MTT, 1994.",
                     "A. D. Yaghjian y S. R. Best, «Impedance, bandwidth, and Q of antennas», IEEE T-AP, 2005.",
                     "IBIS Open Forum, <i>Touchstone File Format Specification</i>, versión 2.0.",
                     "scikit-rf, biblioteca de código abierto para RF (scikit-rf.org)."]),
           Spacer(1, 10),
           P(f"{APP} · versión {version()} · guía personal de {AUTHOR}.", "small")]
    doc.multiBuild(st)


if __name__ == "__main__":
    build(sys.argv[1])
