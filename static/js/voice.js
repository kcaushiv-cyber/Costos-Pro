/* ============================================================
   COSTOS PRO — Sistema de voz (Web Speech API)
   ============================================================ */

const VoiceSystem = (() => {
  let enabled = localStorage.getItem('cp_voice') !== 'false';
  let speed   = parseFloat(localStorage.getItem('cp_voice_speed') || '1.0');
  let volume  = parseFloat(localStorage.getItem('cp_voice_vol')   || '0.85');
  let voiceIndex = parseInt(localStorage.getItem('cp_voice_idx')  || '0');
  let voices  = [];
  let speaking = false;

  const synth = window.speechSynthesis;
  const supported = 'speechSynthesis' in window;

  function loadVoices() {
    voices = synth.getVoices().filter(v => v.lang.startsWith('es'));
    if (!voices.length) voices = synth.getVoices();
  }

  if (supported) {
    loadVoices();
    synth.onvoiceschanged = loadVoices;
  }

  function speak(text, priority = false) {
    if (!supported || !enabled) return;
    if (priority) synth.cancel();
    if (speaking && !priority) return;

    const utt = new SpeechSynthesisUtterance(text);
    utt.lang   = 'es-PE';
    utt.rate   = speed;
    utt.volume = volume;
    if (voices[voiceIndex]) utt.voice = voices[voiceIndex];

    utt.onstart = () => { speaking = true; };
    utt.onend   = () => { speaking = false; };
    utt.onerror = () => { speaking = false; };

    synth.speak(utt);
  }

  function stop() {
    if (supported) synth.cancel();
    speaking = false;
  }

  function toggle() {
    enabled = !enabled;
    localStorage.setItem('cp_voice', enabled);
    _updateBtn();
    if (enabled) speak('Voz activada', true);
    return enabled;
  }

  function setSpeed(v)  { speed  = v; localStorage.setItem('cp_voice_speed', v); }
  function setVolume(v) { volume = v; localStorage.setItem('cp_voice_vol',   v); }
  function setVoice(i)  { voiceIndex = i; localStorage.setItem('cp_voice_idx', i); }
  function isEnabled()  { return enabled; }
  function getVoices()  { return voices; }

  function _updateBtn() {
    const btn = document.getElementById('voice-toggle-btn');
    if (!btn) return;
    btn.classList.toggle('voice-on', enabled);
    btn.title = enabled ? 'Desactivar voz' : 'Activar voz';
    const icon = btn.querySelector('i');
    if (icon) {
      icon.className = enabled ? 'ti ti-volume' : 'ti ti-volume-off';
    }
  }

  // Mensajes contextuales predefinidos
  const MESSAGES = {
    login:     'Bienvenido a Costos Pro, sistema inteligente de gestión de costos.',
    dashboard: 'Panel principal cargado. Aquí puedes ver los indicadores clave de tu empresa.',
    personal:  'Módulo de personal. Registra y gestiona la planilla de trabajadores.',
    products:  'Catálogo de productos y servicios.',
    kardex:    'Módulo de inventario y Kardex.',
    abc:       'Módulo de costeo ABC. Define recursos, centros de actividad y objetos de costo.',
    proceso:   'Módulo de costos por proceso.',
    presupuesto: 'Módulo de presupuestos.',
    calidad:   'Módulo de costos de calidad.',
    manual:    'Manual de usuario interactivo.',
    calc_done: 'Cálculo completado exitosamente.',
    calc_error:'Se detectó un error en los datos. Por favor revisa los campos marcados.',
    export_done:'Archivo exportado y listo para descargar.',
    saved:     'Datos guardados correctamente.',
    deleted:   'Registro eliminado.',
  };

  function sayModule(module) {
    if (MESSAGES[module]) speak(MESSAGES[module]);
  }

  function sayCustom(text, priority = false) {
    speak(text, priority);
  }

  // Auto-anunciar módulo al cargar página
  document.addEventListener('DOMContentLoaded', () => {
    _updateBtn();
    const moduleEl = document.getElementById('page-module-id');
    if (moduleEl) {
      setTimeout(() => sayModule(moduleEl.dataset.module), 800);
    }
    _bindHelpButtons();
  });

  // Botones de ayuda con voz
  function _bindHelpButtons() {
    document.querySelectorAll('[data-voice-help]').forEach(btn => {
      btn.addEventListener('click', () => {
        const text = btn.dataset.voiceHelp;
        if (text) speak(text, true);
      });
    });
  }

  return { speak, stop, toggle, setSpeed, setVolume, setVoice,
           isEnabled, getVoices, sayModule, sayCustom, MESSAGES };
})();

window.CostosProVoice = VoiceSystem;
