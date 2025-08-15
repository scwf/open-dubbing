document.addEventListener('DOMContentLoaded', () => {
  const form = document.getElementById('dubbing-form');
  const statusDiv = document.getElementById('status');
  const engineSelect = document.getElementById('tts_engine');
  const strategySelect = document.getElementById('strategy');
  const languageSelect = document.getElementById('language');

  // Populate options
  fetch('/dubbing/options')
    .then(res => res.json())
    .then(data => {
      (data.tts_engines || []).forEach(e => {
        const opt = document.createElement('option');
        opt.value = e;
        opt.textContent = e;
        engineSelect.appendChild(opt);
      });
      (data.strategies || []).forEach(s => {
        const opt = document.createElement('option');
        opt.value = s;
        opt.textContent = s;
        strategySelect.appendChild(opt);
      });
      (data.languages || []).forEach(l => {
        const opt = document.createElement('option');
        opt.value = l;
        opt.textContent = l;
        languageSelect.appendChild(opt);
      });
    });

  // Submit form
  form.addEventListener('submit', async (e) => {
    e.preventDefault();
    statusDiv.textContent = 'Uploading...';
    const formData = new FormData(form);
    try {
      const response = await fetch('/dubbing', {
        method: 'POST',
        body: formData
      });
      if (!response.ok) throw new Error('Request failed');
      const result = await response.json();
      if (result.result_url) {
        statusDiv.innerHTML = `<a href="${result.result_url}" target="_blank">Download result</a>`;
      } else {
        statusDiv.textContent = 'Completed';
      }
    } catch (err) {
      statusDiv.textContent = 'Error: ' + err.message;
    }
  });
});
