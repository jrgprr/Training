# Sistema Personal de Entrenamiento y Seguimiento

---

## 1. Visión general

Este documento describe el sistema general y coherente para:
- Definir principios de entrenamiento aplicables año tras año
- Tomar decisiones de entrenamiento basadas en el estado
- Evaluar el estado de forma real
- Integrar hábitos diarios de activación y recuperación
- Seguir la evolución mediante un MVP sencillo y fiable (a implementar una aplicación que analice los detalles de entrenamiento)

La planificación anual concreta se documenta por separado en carpetas específicas de cada año.

El sistema está diseñado para:
- Uso personal
- Perfil multideporte (ciclismo, andar, monte, trote) con foco principal en bicicleta
- Entrenamiento autónomo
- Sostenibilidad a largo plazo

Para el registro y análisis del entrenamiento dispongo de: 
- Garmin Fenix 5x Plus
- Báscula Garmin S2
- Garmin Edge 530
- Sensores de potencia Garmin Vector 3 para bicicleta
- Garmin pod running dynamics
- Bicicleta de spinning con sensores de velocidad, cadencia, distancia y potencia
- Cinta de correr

Equipamiento complementario de uso:
- La bicicleta de spinning y la cinta de correr sirven como alternativas de entrenamiento cuando la meteorologia no permite o no aconseja salir fuera.
- Su uso debe respetar la intencion original de la sesion, sustituyendo el medio pero no cambiando de forma agresiva la carga prevista.

---

## 2. Principios fundamentales

1. **El estado manda al plan**, no al revés
2. **Una sola carga principal al día**
3. **Consistencia > heroicidades**
4. **El progreso se basa en semanas repetibles, no en sesiones épicas**
5. **La salud y la continuidad son prioritarias al rendimiento inmediato**
6. **Rutina complementaria diaria por la mañana para activación, movilidad y estiramientos**
7. **Rutina complementaria diaria de paseo nocturno para descarga y regulación del sistema nervioso**
8. **El control del peso se trabaja de forma gradual, sostenible y sin comprometer la capacidad de entrenar**
9. **Cuando la meteorologia sea adversa, se prioriza la continuidad usando alternativas indoor antes que perder la estructura semanal**

---

## 3. Control del peso corporal

El peso corporal forma parte del sistema general porque afecta a:
- salud general,
- sensaciones de entrenamiento,
- eficiencia en la bicicleta,
- y sostenibilidad a medio y largo plazo.

Reglas generales:
- El objetivo de peso no debe perseguirse con medidas agresivas que deterioren recuperación, fuerza o adherencia.
- El peso se interpreta por tendencia, no por variaciones diarias aisladas.
- La pérdida de peso debe apoyar el entrenamiento, no competir con él.
- Si bajar peso empeora de forma clara el descanso, el humor, la fuerza o la repetibilidad semanal, el enfoque debe suavizarse.
- El control del peso se revisa junto con sensaciones, carga y consistencia.

Referencia general:
- El índice aeróbico sigue midiendo solo estímulo aeróbico.
- El peso corporal se usa como eje paralelo de contexto y decisión.

---

## 4. Planificación anual específica

La planificación concreta de cada año se separa del sistema general.

Para 2026, la documentación anual está en:
- [Plan 2026](../2026/Plan-2026.md)
- [Macro 2026](../2026/Macro.md)
- [Meso 2026](../2026/Meso.md)
- [Micro 2026](../2026/Micro.md)

Regla general:
- Los principios de este documento mandan sobre cualquier planificación anual.
- La planificación anual concreta adapta esos principios al contexto real del año.

---

## 5. Rutina diaria de la mañana

Duración total: 40–45 min

- Activación (~20’): respiración, movilidad, glúteos, core
- Movilidad / estiramientos (20–25’): columna, caderas, piernas, respiración

Se realiza todos los días.

---

## 6. Paseos nocturnos

Función:
- Descargar
- Regular sistema nervioso

Uso:
- Días con bici: 20–40 min suaves
- Días sin bici: paseos largos (8–10 km)

Regla clave:
> El paseo solo descarga si no cansa

---

## 7. El MVP: Medidor de estado de forma

### 7.1 Objetivo del MVP

El MVP no prescribe entrenamientos. Su función es responder a una pregunta clave:

> *¿Mi forma física está mejorando, manteniéndose o empeorando?*

Sirve como **instrumento de decisión**, no como entrenador automático.

La operativa tecnica del MVP, incluyendo base de datos, servicios, analisis y front-end, se desarrolla en:
- [Arquitectura MVP 2026](../MVP/MVP-Arquitectura.md)

---

### 7.2 Índice Aeróbico

Basado en:
- Carga aeróbica semanal
- Comparación entre carga reciente y carga histórica

Concepto:
- Carga corta: media de 2 semanas
- Carga larga: media de 6 semanas

Interpretación orientativa:
- < 95 → forma baja / retorno
- 95–100 → base funcional
- 100–105 → buena forma
- 105–108 → forma alta
- >108 → posible fatiga acumulada

El índice:
- No incluye fuerza, peso ni alimentación
- Representa únicamente el estímulo aeróbico

---

### 7.3 Indicador de Tendencia de Peso

Es una métrica paralela del MVP para responder a otra pregunta clave:

> *¿El peso corporal está evolucionando en la dirección deseada sin perjudicar el entrenamiento?*

Objetivo:
- dar seguimiento al proceso de control del peso,
- detectar si la tendencia real acompaña al plan,
- y comprobar si la pérdida de peso sigue siendo compatible con energía, recuperación y consistencia.

Concepto:
- Peso corto: media de 2 semanas.
- Peso largo: media de 6 semanas.
- La referencia principal es la tendencia, no una pesada aislada.

Interpretación orientativa:
- Tendencia descendente suave y estable → escenario favorable.
- Tendencia plana → mantenimiento o necesidad de revisar hábitos.
- Descenso demasiado rápido con peores sensaciones → posible coste excesivo.
- Tendencia ascendente sostenida no buscada → revisar estructura diaria, actividad y alimentación.

El indicador:
- No sustituye al índice aeróbico.
- No mide rendimiento.
- Mide la dirección del peso corporal y su compatibilidad con entrenar bien.

---

### 7.4 Análisis paralelos (contexto)

No modifican el índice, pero ayudan a interpretarlo:
- Frecuencia de fuerza
- Sensaciones subjetivas
- Paseos y actividad ligera
- Peso corporal (tendencia)
- Alimentación (cualitativa)

En el caso del peso corporal, interesa observar:
- tendencia de 2 a 6 semanas,
- relacion entre peso, sensaciones y rendimiento,
- y si la evolucion del peso esta siendo compatible con entrenar bien.

---

## 8. Evaluación del estado de forma

El estado de forma se evalúa usando:
- Últimas 6–8 semanas reales
- Valor y tendencia del índice aeróbico
- Valor y tendencia del indicador de peso
- Consistencia del entrenamiento
- Nivel de fuerza mantenido
- Sensaciones generales

Interpretación general:
> El estado de forma debe evaluarse en contexto, no por un dato aislado.

---

## 9. Uso del MVP para ajustar

Revisión semanal:
- Índice aeróbico
- Indicador de tendencia de peso
- Tendencia
- Sensaciones
- Tendencia del peso corporal

Decisión:
- Semana repetible → se puede progresar
- Semana con deuda → mantener o reducir

Lectura combinada:
- Índice aeróbico mejorando + peso bajando bien → progreso limpio.
- Índice estable + peso bajando bien → fase útil de recomposición o ajuste.
- Índice cayendo + peso bajando demasiado rápido → probable exceso de restricción o fatiga.
- Índice bien + peso subiendo sin intención → revisar hábitos antes de aumentar carga.

---

## 10. Filosofía final

> Este sistema no busca entrenar más.
> Busca entrenar mejor durante más años.

El éxito es encajar semanas normales durante meses.

---