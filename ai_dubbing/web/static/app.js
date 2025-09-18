document.addEventListener('DOMContentLoaded', () => {
  const form = document.getElementById('dubbing-form');
  const statusSection = document.getElementById('status-section');
  const statusTitle = document.getElementById('status-title');
  const statusMessage = document.getElementById('status-message');
  const progressContainer = document.getElementById('progress-container');
  const progressFill = document.getElementById('progress-fill');
  const progressText = document.getElementById('progress-text');
  const resultSection = document.getElementById('result-section');
  const downloadLink = document.getElementById('download-link');
  const submitBtn = document.getElementById('submit-btn');

  // Optimization status elements
  const optimizationStatusSection = document.getElementById('optimization-status-section');
  const optimizationStatusTitle = document.getElementById('optimization-status-title');
  const optimizationStatusMessage = document.getElementById('optimization-status-message');
  const optimizationProgressContainer = document.getElementById('optimization-progress-container');
  const optimizationProgressFill = document.getElementById('optimization-progress-fill');
  const optimizationProgressText = document.getElementById('optimization-progress-text');
  const optimizationResultSection = document.getElementById('optimization-result-section');
  const optimizationDownloadLink = document.getElementById('optimization-download-link');

  // Dubbing status elements
  const dubbingStatusSection = document.getElementById('dubbing-status-section');
  const dubbingStatusTitle = document.getElementById('dubbing-status-title');
  const dubbingStatusMessage = document.getElementById('dubbing-status-message');
  const dubbingProgressContainer = document.getElementById('dubbing-progress-container');
  const dubbingProgressFill = document.getElementById('dubbing-progress-fill');
  const dubbingProgressText = document.getElementById('dubbing-progress-text');
  const dubbingResultSection = document.getElementById('dubbing-result-section');
  const dubbingDownloadLink = document.getElementById('dubbing-download-link');

  // Subtitle optimization elements
  const optimizationForm = document.getElementById('optimization-form');
  const optimizeBtn = document.getElementById('optimize-btn');

  const engineSelect = document.getElementById('tts_engine');
  const strategySelect = document.getElementById('strategy');
  const languageSelect = document.getElementById('language');

  // --- NEW ---
  const voicePairsContainer = document.getElementById('voice-pairs-container');
  const addVoicePairBtn = document.getElementById('add-voice-pair-btn');
  const globalVoiceModeRadios = document.querySelectorAll('input[name="global_voice_mode"]');
  let builtInAudios = {};
  let currentTaskInterval = null;

  // --- Main Initialization ---
  async function initApp() {
    await loadBuiltInAudios();
    setupVoicePairControls();

    // Setup the rest of the application
    loadOptions();
    loadConfig();
    setupFileUploads();
    setupFormSubmission();
    setupOptimizationForm();
    setupTabs();
    setupMainTabs();
    setupIndexTTS2Controls();
    setupPasswordToggle();
    setupTextInput();
    setupInputMode();
  }

  // --- Data Loading ---
  async function loadBuiltInAudios() {
    try {
      const response = await fetch('/dubbing/built-in-audios');
      if (!response.ok) throw new Error(`HTTP ${response.status}`);
      builtInAudios = await response.json();
    } catch (error) {
      console.error('Failed to load built-in audios:', error);
      showError('加载内置音频列表失败');
    }
  }

  // --- Voice Pair Management ---
  function setupVoicePairControls() {
    addVoicePairBtn.addEventListener('click', () => createVoicePair());
    globalVoiceModeRadios.forEach(radio => {
      radio.addEventListener('change', () => updateAllVoicePairs());
    });
    if (voicePairsContainer.children.length === 0) {
      createVoicePair(); // Add the first pair initially
    }
  }

  function createVoicePair() {
    const pairDiv = document.createElement('div');
    pairDiv.classList.add('voice-pair');

    pairDiv.innerHTML = `
      <div class="voice-pair-content">
        <div class="audio-source-wrapper"></div>
        <textarea name="prompt_texts" placeholder="输入参考文本..." class="form-textarea" required></textarea>
        <button type="button" class="remove-pair-btn"><i class="fas fa-trash"></i></button>
      </div>
    `;

    pairDiv.querySelector('.remove-pair-btn').addEventListener('click', () => pairDiv.remove());

    voicePairsContainer.appendChild(pairDiv);
    updateVoicePairContent(pairDiv); // Initialize based on global mode
  }

  function updateAllVoicePairs() {
    const voicePairs = document.querySelectorAll('.voice-pair');
    voicePairs.forEach(pairDiv => updateVoicePairContent(pairDiv));
  }

  function updateVoicePairContent(pairDiv) {
    const selectedMode = document.querySelector('input[name="global_voice_mode"]:checked').value;
    const sourceWrapper = pairDiv.querySelector('.audio-source-wrapper');
    const promptTextarea = pairDiv.querySelector('textarea[name="prompt_texts"]');

    if (selectedMode === 'custom_upload') {
      sourceWrapper.innerHTML = `
        <div class="file-upload-area" data-type="voice">
          <input type="file" name="voice_files" accept=".wav,.mp3" required class="file-input">
          <div class="upload-content">
            <i class="fas fa-cloud-upload-alt"></i>
            <p>选择语音文件</p>
            <span class="file-name">未选择</span>
          </div>
        </div>`;
      promptTextarea.value = '';
      const input = sourceWrapper.querySelector('.file-input');
      input.addEventListener('change', (e) => handleFileSelection(e, sourceWrapper.querySelector('.file-upload-area'), 'voice'));
    } else {
      // For built-in mode, show a selector for built-in audios
      createBuiltInAudioSelector(sourceWrapper, promptTextarea);
    }
  }

  function createBuiltInAudioSelector(sourceWrapper, promptTextarea) {
    const selectHtml = Object.keys(builtInAudios).map(name => 
      `<option value="${name}">${name}</option>`
    ).join('');

    sourceWrapper.innerHTML = `
      <div class="built-in-audio-selector">
        <label class="form-label">选择内置音频</label>
        <select class="built-in-audio-select form-select">
          <option value="">请选择内置音频</option>
          ${selectHtml}
        </select>
      </div>`;

    const select = sourceWrapper.querySelector('.built-in-audio-select');
    select.addEventListener('change', (e) => {
      const selectedAudio = e.target.value;
      if (selectedAudio && builtInAudios[selectedAudio]) {
        const audioData = builtInAudios[selectedAudio];
        promptTextarea.value = audioData.text;
        
        // Store the path for form submission
        sourceWrapper.dataset.builtInPath = audioData.path;
        sourceWrapper.dataset.builtInName = selectedAudio;
      } else {
        promptTextarea.value = '';
        delete sourceWrapper.dataset.builtInPath;
        delete sourceWrapper.dataset.builtInName;
      }
    });
  }

  // --- Form Validation ---
  function validateForm() {
    let isValid = true;
    form.querySelectorAll('.error-field').forEach(el => el.classList.remove('error-field'));

    const inputMode = document.querySelector('input[name="input_mode"]:checked').value;
    if (inputMode === 'file') {
        const fileInput = document.querySelector('input[name="input_file"]');
        if (!fileInput || fileInput.files.length === 0) {
            isValid = false;
            fileInput.closest('.file-upload-area').classList.add('error-field');
        }
    } else {
        const textInput = document.querySelector('textarea[name="input_text"]');
        if (!textInput || !textInput.value.trim()) {
            isValid = false;
            textInput.classList.add('error-field');
        }
    }

    const voicePairs = document.querySelectorAll('.voice-pair');
    if (voicePairs.length === 0) {
        isValid = false;
    }
    voicePairs.forEach(pair => {
        const promptText = pair.querySelector('textarea[name="prompt_texts"]');
        if (!promptText || !promptText.value.trim()) {
            isValid = false;
            if(promptText) promptText.classList.add('error-field');
        }

        const globalMode = document.querySelector('input[name="global_voice_mode"]:checked').value;
        if (globalMode === 'custom_upload') {
            const fileInput = pair.querySelector('input[type="file"][name="voice_files"]');
            if (!fileInput || fileInput.files.length === 0) {
                isValid = false;
                const uploadArea = pair.querySelector('.file-upload-area');
                if (uploadArea) uploadArea.classList.add('error-field');
            }
        } else if (globalMode === 'built_in') {
            const sourceWrapper = pair.querySelector('.audio-source-wrapper');
            if (!sourceWrapper.dataset.builtInPath) {
                isValid = false;
                const selector = pair.querySelector('.built-in-audio-select');
                if (selector) selector.classList.add('error-field');
            }
        }
    });

    if (!isValid) showError('请填写所有必填字段。');
    return isValid;
  }

  // --- Form Submission ---
  async function handleFormSubmit(e) {
    e.preventDefault();
    if (!validateForm()) return;

    cleanupDubbingTask();
    setFormLoading(true);
    dubbingStatusSection.style.display = 'block';
    showDubbingStatus('准备中...', '正在准备文件上传...');
    const formData = new FormData();

    // Main form data
    ['tts_engine', 'strategy', 'language', 'input_mode', 'text_format', 'input_text'].forEach(id => {
        const el = form.elements[id];
        if(el) formData.append(id, el.value);
    });
    const inputFile = form.elements['input_file'];
    if (inputFile && inputFile.files.length > 0) {
        formData.append('input_file', inputFile.files[0]);
    }

    // Voice pairs data
    const globalMode = document.querySelector('input[name="global_voice_mode"]:checked').value;
    document.querySelectorAll('.voice-pair').forEach(pair => {
        const promptText = pair.querySelector('textarea[name="prompt_texts"]').value;
        const sourceWrapper = pair.querySelector('.audio-source-wrapper');
        
        if (globalMode === 'custom_upload') {
            const fileInput = pair.querySelector('input[type="file"][name="voice_files"]');
            if (fileInput && fileInput.files.length > 0) {
                formData.append('upload_voice_files', fileInput.files[0]);
                formData.append('builtin_voice_files', '');
                formData.append('prompt_texts', promptText);
            }
        } else if (globalMode === 'built_in') {
            if (sourceWrapper.dataset.builtInPath) {
                formData.append('upload_voice_files', new Blob(), '');
                formData.append('builtin_voice_files', sourceWrapper.dataset.builtInPath);
                formData.append('prompt_texts', promptText);
            }
        }
    });

    // Append advanced config inputs
    const configInputs = document.querySelectorAll('#tab-concurrency input');
    configInputs.forEach(input => formData.append(input.name, input.value));

    // Append IndexTTS2 emotion control parameters (only if IndexTTS2 is selected)
    const selectedEngine = document.getElementById('tts_engine').value;
    if (selectedEngine === 'index_tts2') {
      // Emotion mode
      const emotionMode = document.getElementById('emotion_mode');
      if (emotionMode) {
        formData.append('emotion_mode', emotionMode.value);
      }

      // Emotion audio file
      const emotionAudioFile = document.getElementById('emotion_audio_file');
      if (emotionAudioFile && emotionAudioFile.files.length > 0) {
        formData.append('emotion_audio_file', emotionAudioFile.files[0]);
      }

      // Emotion vector
      const emotionVector = document.getElementById('emotion_vector');
      if (emotionVector && emotionVector.value.trim()) {
        formData.append('emotion_vector', emotionVector.value.trim());
      }

      // Emotion text
      const emotionText = document.getElementById('emotion_text');
      if (emotionText && emotionText.value.trim()) {
        formData.append('emotion_text', emotionText.value.trim());
      }

      // Emotion alpha
      const emotionAlpha = document.getElementById('emotion_alpha');
      if (emotionAlpha) {
        formData.append('emotion_alpha', emotionAlpha.value);
      }

      // Use random
      const useRandom = document.getElementById('use_random');
      if (useRandom) {
        formData.append('use_random', useRandom.checked);
      }
    }

    try {
        const response = await fetch('/dubbing', { method: 'POST', body: formData });
        if (!response.ok) {
            const errorText = await response.text();
            throw new Error(`请求失败: ${response.status} - ${errorText}`);
        }
        const result = await response.json();
        if (result.task_id) {
            pollTaskStatus(result.task_id);
        } else {
            showError('未能获取任务ID');
        }
    } catch (error) {
        console.error('Submission error:', error);
        showDubbingError(`配音失败: ${error.message}`);
    } finally {
        setFormLoading(false);
    }
  }

  // --- All other original functions restored below ---

  document.addEventListener('click', (e) => {
    if (e.target.closest('.file-upload-area') && e.target.tagName !== 'INPUT') {
      const uploadArea = e.target.closest('.file-upload-area');
      const input = uploadArea.querySelector('.file-input');
      if (input) input.click();
    }
  });

  function setupPasswordToggle() {
    document.addEventListener('click', e => {
      if (e.target.classList.contains('toggle-password')) {
        const icon = e.target;
        const input = icon.previousElementSibling;
        if (input && input.tagName === 'INPUT') {
          if (input.type === 'password') {
            input.type = 'text';
            icon.classList.replace('fa-eye', 'fa-eye-slash');
          } else {
            input.type = 'password';
            icon.classList.replace('fa-eye-slash', 'fa-eye');
          }
        }
      }
    });
  }

  async function loadOptions() {
    try {
      showLoadingState();
      const response = await fetch('/dubbing/options');
      if (!response.ok) throw new Error(`HTTP ${response.status}: ${response.statusText}`);
      const data = await response.json();
      populateSelect(engineSelect, data.tts_engines || [], 'TTS 引擎', 'fish_speech');
      populateSelect(strategySelect, data.strategies || [], '策略', 'stretch');
      populateSelect(languageSelect, data.languages || [], '语言');
    } catch (error) {
      console.error('Failed to load options:', error);
      showError('加载配置选项失败，请刷新页面重试');
    } finally {
      hideLoadingState();
    }
  }

  function showLoadingState() { [engineSelect, strategySelect, languageSelect].forEach(s => { s.innerHTML = '<option value="">加载中...</option>'; s.disabled = true; }); }
  function hideLoadingState() { [engineSelect, strategySelect, languageSelect].forEach(s => { s.disabled = false; }); }

  function populateSelect(select, options, placeholder, defaultValue = null) {
    select.innerHTML = '';
    const placeholderOpt = document.createElement('option');
    placeholderOpt.value = '';
    placeholderOpt.textContent = `选择${placeholder}`;
    placeholderOpt.disabled = true;
    select.appendChild(placeholderOpt);
    options.forEach(option => {
      const opt = document.createElement('option');
      opt.value = option;
      opt.textContent = option;
      if (option === defaultValue) opt.selected = true;
      select.appendChild(opt);
    });
  }

  function setupTabs() {
    const tabLinks = document.querySelectorAll('.tab-link');
    const tabContents = document.querySelectorAll('.tab-content');

    tabLinks.forEach(link => {
      link.addEventListener('click', () => {
        const tabId = link.dataset.tab;

        // 移除所有标签页的active状态
        tabLinks.forEach(l => l.classList.remove('active'));
        tabContents.forEach(c => {
          c.classList.remove('active');
          c.style.display = 'none'; // 确保隐藏
        });

        // 激活当前标签页
        link.classList.add('active');
        const targetContent = document.getElementById(tabId);
        if (targetContent) {
          targetContent.classList.add('active');
          targetContent.style.display = 'block'; // 确保显示
        }
      });
    });
  }

  function setupMainTabs() {
    const mainTabLinks = document.querySelectorAll('.main-tab-link');
    const mainTabContents = document.querySelectorAll('.main-tab-content');

    mainTabLinks.forEach(link => {
      link.addEventListener('click', () => {
        const tabId = link.dataset.tab;

        // Remove active class from all main tab links and contents
        mainTabLinks.forEach(l => l.classList.remove('active'));
        mainTabContents.forEach(c => c.classList.remove('active'));

        // Add active class to clicked link and corresponding content
        link.classList.add('active');
        const targetTab = document.getElementById(tabId);
        if (targetTab) {
          targetTab.classList.add('active');
        }

        // Log tab switch for debugging
        if (window.location.hostname === 'localhost' || window.location.hostname === '127.0.0.1') {
          console.log('切换到标签页:', tabId);
        }
      });
    });
  }

  // 统一的配置加载和设置函数
  function setConfigFieldValue(selector, value) {
    const field = document.querySelector(selector);
    if (field && value !== undefined && value !== null && value !== '') {
      field.value = value;
    }
  }

async function loadConfig() {
    try {
      const response = await fetch('/dubbing/config');
      const data = await response.json();

      // Set basic configuration values
      if (data.basic) {
        setConfigFieldValue('#tts_engine', data.basic.tts_engine);
        setConfigFieldValue('#strategy', data.basic.strategy);
      }

      // Set time borrowing configuration values in optimization tab
      if (data.time_borrowing) {
          setTimeout(() => {
          setConfigFieldValue('input[name="opt_min_gap_threshold"]', data.time_borrowing.min_gap_threshold);
          setConfigFieldValue('input[name="opt_borrow_ratio"]', data.time_borrowing.borrow_ratio);
          setConfigFieldValue('input[name="opt_extra_buffer"]', data.time_borrowing.extra_buffer);
          }, 100);
      }

      // Set subtitle optimization configuration values in optimization tab
      if (data.subtitle_optimization) {
          setTimeout(() => {
          setConfigFieldValue('input[name="opt_llm_api_key"]', data.subtitle_optimization.llm_api_key);
          setConfigFieldValue('input[name="opt_llm_model"]', data.subtitle_optimization.llm_model);
          setConfigFieldValue('input[name="opt_base_url"]', data.subtitle_optimization.base_url);
          setConfigFieldValue('input[name="opt_llm_max_concurrency"]', data.subtitle_optimization.llm_max_concurrency);
          setConfigFieldValue('input[name="opt_chinese_char_min_time"]', data.subtitle_optimization.chinese_char_min_time);
          setConfigFieldValue('input[name="opt_english_word_min_time"]', data.subtitle_optimization.english_word_min_time);
          setConfigFieldValue('input[name="opt_llm_max_retries"]', data.subtitle_optimization.llm_max_retries);
          setConfigFieldValue('input[name="opt_llm_timeout"]', data.subtitle_optimization.llm_timeout);
          }, 100);
      }

      // Populate concurrency tab content
      const concurrencyTab = document.getElementById('tab-concurrency');
      if (concurrencyTab && data.concurrency) {
      concurrencyTab.innerHTML = `
        <div class="options-row">
          <div class="form-group">
            <label class="form-label"><i class="fas fa-bolt"></i> TTS最大并发数</label>
            <input type="number" name="tts_max_concurrency" class="form-select" value="${data.concurrency.tts_max_concurrency}">
          </div>
          <div class="form-group">
            <label class="form-label"><i class="fas fa-redo"></i> TTS最大重试次数</label>
            <input type="number" name="tts_max_retries" class="form-select" value="${data.concurrency.tts_max_retries}">
          </div>
        </div>
      `;
      }

      return data.basic;
    } catch (error) {
      console.error('Failed to load config:', error);
      return null;
    }
  }

  // Get form configuration data for saving
  function getFormConfig() {
    const config = {
      concurrency: {
        tts_max_concurrency: document.querySelector('[name="tts_max_concurrency"]')?.value || '',
        tts_max_retries: document.querySelector('[name="tts_max_retries"]')?.value || '',
      },
      subtitle_optimization: {
        llm_api_key: document.querySelector('input[name="opt_llm_api_key"]')?.value || '',
        llm_model: document.querySelector('input[name="opt_llm_model"]')?.value || '',
        base_url: document.querySelector('input[name="opt_base_url"]')?.value || '',
        chinese_char_min_time: document.querySelector('input[name="opt_chinese_char_min_time"]')?.value || '',
        english_word_min_time: document.querySelector('input[name="opt_english_word_min_time"]')?.value || '',
        llm_max_concurrency: document.querySelector('input[name="opt_llm_max_concurrency"]')?.value || '',
        llm_max_retries: document.querySelector('input[name="opt_llm_max_retries"]')?.value || '',
        llm_timeout: document.querySelector('input[name="opt_llm_timeout"]')?.value || '',
      },
      time_borrowing: {
        min_gap_threshold: document.querySelector('input[name="opt_min_gap_threshold"]')?.value || '',
        borrow_ratio: document.querySelector('input[name="opt_borrow_ratio"]')?.value || '',
        extra_buffer: document.querySelector('input[name="opt_extra_buffer"]')?.value || '',
      }
    };

    // Add IndexTTS2 emotion control parameters if IndexTTS2 is selected
    const selectedEngine = document.getElementById('tts_engine')?.value;
    if (selectedEngine === 'index_tts2') {
      config.index_tts2_emotion = {
        emotion_mode: document.getElementById('emotion_mode')?.value || 'auto',
        emotion_vector: document.getElementById('emotion_vector')?.value || '',
        emotion_text: document.getElementById('emotion_text')?.value || '',
        emotion_alpha: document.getElementById('emotion_alpha')?.value || '0.8',
        use_random: document.getElementById('use_random')?.checked || false,
      };
    }

    return config;
  }

  // Setup input mode switching
  function setupInputMode() {
    const inputModeRadios = document.querySelectorAll('input[name="input_mode"]');
    const fileUploadSection = document.getElementById('file-upload-section');
    const textInputSection = document.getElementById('text-input-section');

    inputModeRadios.forEach(radio => {
      radio.addEventListener('change', function() {
        if (this.value === 'file') {
          fileUploadSection.style.display = 'block';
          textInputSection.style.display = 'none';
          // Make file input required when file mode is selected
          const fileInput = document.querySelector('input[name="input_file"]');
          if (fileInput) fileInput.required = true;
          // Remove text input requirement
          const textInput = document.querySelector('textarea[name="input_text"]');
          if (textInput) textInput.required = false;
        } else if (this.value === 'text') {
          fileUploadSection.style.display = 'none';
          textInputSection.style.display = 'block';
          // Make text input required when text mode is selected
          const textInput = document.querySelector('textarea[name="input_text"]');
          if (textInput) textInput.required = true;
          // Remove file input requirement
          const fileInput = document.querySelector('input[name="input_file"]');
          if (fileInput) fileInput.required = false;
        }
      });
    });
  }

  // Setup text input functionality
  function setupTextInput() {
    const textInput = document.getElementById('input_text');
    const charCount = document.querySelector('.char-count');

    if (textInput && charCount) {
      textInput.addEventListener('input', function() {
        const count = this.value.length;
        charCount.textContent = `字符数: ${count}`;
      });
    }
  }

  // Setup file upload functionality
  function setupFileUploads() {
    const uploadAreas = document.querySelectorAll('.file-upload-area');
    const fileInputs = document.querySelectorAll('.file-input');
    uploadAreas.forEach((area, index) => {
      const input = fileInputs[index];
      const fileType = area.dataset.type;

      // File selection change
      input.addEventListener('change', (e) => handleFileSelection(e, area, fileType));

      // Drag and drop
      area.addEventListener('dragover', handleDragOver);
      area.addEventListener('dragleave', handleDragLeave);
      area.addEventListener('drop', (e) => handleDrop(e, area, input, fileType));

      // Prevent default drag behaviors
      area.addEventListener('dragenter', (e) => e.preventDefault());
    });

    // Setup input mode switching
    setupInputMode();

    // Setup text input character count
    setupTextInput();
  }

  function handleFileSelection(event, area, fileType) {
    const files = event.target.files;
    updateFileDisplay(area, files, fileType);
  }

  function handleDragOver(e) {
    e.preventDefault();
    e.currentTarget.classList.add('dragover');
  }

  function handleDragLeave(e) {
    e.preventDefault();
    e.currentTarget.classList.remove('dragover');
  }

  function handleDrop(e, area, input, fileType) {
    e.preventDefault();
    area.classList.remove('dragover');

    const files = e.dataTransfer.files;
    input.files = files;
    updateFileDisplay(area, files, fileType);
    validateForm();
  }

  function updateFileDisplay(area, files, fileType) {
    const fileNameSpan = area.querySelector('.file-name');
    const uploadContent = area.querySelector('.upload-content');

    if (files.length > 0) {
      if (fileType === 'voice' && files.length > 1) {
        fileNameSpan.textContent = `已选择 ${files.length} 个文件`;
        fileNameSpan.style.color = '#10b981';
      } else {
        fileNameSpan.textContent = files[0].name;
        fileNameSpan.style.color = '#10b981';
      }

      // Update icon and text
      uploadContent.innerHTML = `
        <i class="fas fa-check-circle" style="color: #10b981;"></i>
        <p>文件已选择</p>
        <span class="file-name" style="color: #10b981;">${fileNameSpan.textContent}</span>
      `;
    } else {
      fileNameSpan.textContent = '未选择文件';
      fileNameSpan.style.color = '#999';

      // Reset to default
      uploadContent.innerHTML = `
        <i class="fas fa-cloud-upload-alt"></i>
        <p>点击选择文件或拖拽到此处</p>
        <span class="file-name">未选择文件</span>
      `;
    }
  }

  // Setup form validation
  function setupFormValidation() {
    // Validation will now only run on submit
  }

  // Setup form submission
  function setupFormSubmission() {
    form.addEventListener('submit', handleFormSubmit);
  }

  // Setup optimization form
  function setupOptimizationForm() {
    if (optimizationForm) {
      optimizationForm.addEventListener('submit', handleOptimizationSubmit);

      // Setup file upload for optimization form
      const optimizationArea = optimizationForm.querySelector('.file-upload-area');
      const optimizationInput = optimizationForm.querySelector('.file-input');

      if (optimizationArea && optimizationInput) {
        optimizationInput.addEventListener('change', (e) => handleFileSelection(e, optimizationArea, 'optimization-srt'));
        optimizationArea.addEventListener('dragover', handleDragOver);
        optimizationArea.addEventListener('dragleave', handleDragLeave);
        optimizationArea.addEventListener('drop', (e) => handleDrop(e, optimizationArea, optimizationInput, 'optimization-srt'));
        optimizationArea.addEventListener('dragenter', (e) => e.preventDefault());
      }
    }
  }

  async function handleOptimizationSubmit(e) {
    e.preventDefault();

    const optimizationFile = optimizationForm.querySelector('input[name="input_file"]');

    if (!optimizationFile.files.length) {
      showError('请选择要优化的 SRT 文件');
      return;
    }

    // 检查文件类型
    const file = optimizationFile.files[0];
    if (!file.name.toLowerCase().endsWith('.srt')) {
      showError('仅支持 .srt 格式的字幕文件');
      return;
    }

    // 清理之前的任务状态
    cleanupOptimizationTask();

    showOptimizationStatus('准备中...', '正在保存配置并准备字幕优化...');
    optimizationStatusSection.style.display = 'block';
    setOptimizationLoading(true);

    try {
      // 首先保存字幕优化配置
      const configData = getFormConfig();

      // 保存配置
      await fetch('/dubbing/config', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify(configData),
      });

      showOptimizationStatus('准备中...', '配置已保存，正在开始字幕优化...');

      const formData = new FormData();
      formData.append('input_file', file);

      const response = await fetch('/subtitle-optimization', {
        method: 'POST',
        body: formData
      });

      if (!response.ok) {
        const errorText = await response.text();
        throw new Error(`请求失败: ${response.status} - ${errorText}`);
      }

      const result = await response.json();

      if (result.task_id) {
        pollTaskStatus(result.task_id, 'optimization');
      } else {
        showError('未能获取任务ID');
      }

    } catch (error) {
      console.error('Optimization error:', error);
      showOptimizationError(`字幕优化失败: ${error.message}`);
      setOptimizationLoading(false);
    }
  }

  function setOptimizationLoading(loading) {
    if (loading) {
      optimizeBtn.disabled = true;
      optimizeBtn.innerHTML = '<i class="fas fa-spinner fa-spin"></i><span>优化中...</span>';
    } else {
      optimizeBtn.disabled = false;
      optimizeBtn.innerHTML = '<i class="fas fa-magic"></i><span>开始优化</span>';
    }
  }

  async function pollTaskStatus(taskId, taskType = 'dubbing') {
    if (taskType === 'optimization') {
      showOptimizationProgress();
    } else {
      showDubbingProgress();
    }

    // 根据任务类型确定状态查询URL
    const statusUrl = taskType === 'optimization'
      ? `/subtitle-optimization/status/${taskId}`
      : `/dubbing/status/${taskId}`;

    // 定义状态检查函数
    const checkStatus = async () => {
      try {
        const response = await fetch(statusUrl);
        if (!response.ok) {
          throw new Error('无法获取任务状态');
        }

        const data = await response.json();

        // 只在开发模式下显示详细日志
        if (window.location.hostname === 'localhost' || window.location.hostname === '127.0.0.1') {
          console.log('任务状态更新:', {
            taskId,
            taskType,
            status: data.status,
            progress: data.progress,
            message: data.message
          });
        }

        // 根据任务类型更新状态
        if (taskType === 'optimization') {
          optimizationStatusTitle.textContent = '字幕优化中...';
          optimizationStatusMessage.textContent = data.message || `当前进度: ${data.progress}%`;
          updateOptimizationProgress(data.progress);
        } else {
          dubbingStatusTitle.textContent = '配音处理中...';
          dubbingStatusMessage.textContent = data.message || `当前进度: ${data.progress}%`;
          updateDubbingProgress(data.progress);
        }

        if (data.status === 'completed') {
          if (currentTaskInterval) {
            clearInterval(currentTaskInterval);
            currentTaskInterval = null;
          }
          // 根据任务类型显示结果
          if (taskType === 'optimization') {
            showOptimizationResult(data.result_url);
            setOptimizationLoading(false);
          } else {
            showDubbingResult(data.result_url);
            setFormLoading(false);
          }
          return true; // 任务完成
        } else if (data.status === 'failed') {
          if (currentTaskInterval) {
            clearInterval(currentTaskInterval);
            currentTaskInterval = null;
          }
          if (taskType === 'optimization') {
            showOptimizationError(`字幕优化失败: ${data.error || '未知错误'}`);
            setOptimizationLoading(false);
          } else {
            showDubbingError(`配音失败: ${data.error || '未知错误'}`);
            setFormLoading(false);
          }
          return true; // 任务失败
        }
        return false; // 继续轮询
      } catch (error) {
        console.error('Polling error:', error);
        if (currentTaskInterval) {
          clearInterval(currentTaskInterval);
          currentTaskInterval = null;
        }
        if (taskType === 'optimization') {
          showOptimizationError('无法轮询任务状态');
          setOptimizationLoading(false);
        } else {
          showDubbingError('无法轮询任务状态');
          setFormLoading(false);
        }
        return true; // 停止轮询
      }
    };

    // 立即执行第一次检查，避免等待轮询间隔
    if (await checkStatus()) {
      return; // 任务已完成或失败，无需轮询
    }

    // 设置高频轮询以捕获快速状态变化 (500ms间隔)
    currentTaskInterval = setInterval(async () => {
      if (await checkStatus()) {
        if (currentTaskInterval) {
          clearInterval(currentTaskInterval);
          currentTaskInterval = null;
        }
      }
    }, 500);
  }

  function setFormLoading(loading) {
    if (loading) {
      form.classList.add('loading');
      submitBtn.disabled = true;
      submitBtn.innerHTML = '<i class="fas fa-spinner fa-spin"></i><span>处理中...</span>';
    } else {
      form.classList.remove('loading');
      submitBtn.disabled = false;
      submitBtn.innerHTML = '<i class="fas fa-play"></i><span>开始配音</span>';
    }
  }

  function showDubbingStatus(title, message) {
    dubbingStatusTitle.textContent = title;
    dubbingStatusMessage.textContent = message;
    dubbingProgressContainer.style.display = 'none';
    dubbingResultSection.style.display = 'none';
  }

  function showOptimizationStatus(title, message) {
    optimizationStatusTitle.textContent = title;
    optimizationStatusMessage.textContent = message;
    optimizationProgressContainer.style.display = 'none';
    optimizationResultSection.style.display = 'none';
  }

  function showDubbingError(message) {
    showDubbingStatus('配音失败', message);
    dubbingProgressContainer.style.display = 'none';

    // Show error in dubbing status section
    dubbingStatusSection.style.display = 'block';

    // Auto-hide after 8 seconds
    setTimeout(() => {
      if (dubbingStatusTitle.textContent === '配音失败') {
        dubbingStatusSection.style.display = 'none';
      }
    }, 8000);
  }

  function showError(message) {
    showStatus('错误', message);
    progressContainer.style.display = 'none';

    // Show error in status section
    statusSection.style.display = 'block';

    // Auto-hide after 8 seconds
    setTimeout(() => {
      if (statusTitle.textContent === '错误') {
        statusSection.style.display = 'none';
      }
    }, 8000);
  }

  function showStatus(title, message) {
    statusTitle.textContent = title;
    statusMessage.textContent = message;
    progressContainer.style.display = 'none';
    resultSection.style.display = 'none';
  }

  function showDubbingProgress() {
    showDubbingStatus('配音处理中...', '正在处理配音...');
    dubbingProgressContainer.style.display = 'block';
  }

  function updateDubbingProgress(progress) {
    dubbingProgressFill.style.width = `${progress}%`;
    dubbingProgressText.textContent = `${Math.round(progress)}%`;
  }

  function showOptimizationProgress() {
    showOptimizationStatus('字幕优化中...', '正在处理字幕优化...');
    optimizationProgressContainer.style.display = 'block';
  }

  function updateOptimizationProgress(progress) {
    optimizationProgressFill.style.width = `${progress}%`;
    optimizationProgressText.textContent = `${Math.round(progress)}%`;
  }

  function showOptimizationResult(resultUrl) {
    const fileName = resultUrl.split('/').pop();
    
    // 添加CSS类来隐藏状态内容
    optimizationStatusSection.classList.add('show-result');
    
    // 设置下载链接
    optimizationDownloadLink.href = resultUrl;
    optimizationDownloadLink.download = fileName;
    
    // 显示结果区域，隐藏进度条
    optimizationResultSection.style.display = 'block';
    optimizationProgressContainer.style.display = 'none';
    
    // Add success animation
    optimizationResultSection.classList.add('success-animation');
    setTimeout(() => {
      optimizationResultSection.classList.remove('success-animation');
    }, 600);
  }

  function cleanupOptimizationTask() {
    // 清理之前的轮询interval
    if (currentTaskInterval) {
      clearInterval(currentTaskInterval);
      currentTaskInterval = null;
    }
    
    // 移除结果显示类
    optimizationStatusSection.classList.remove('show-result');
    
    // 重置状态界面元素的显示状态
    optimizationStatusTitle.style.display = '';
    optimizationStatusMessage.style.display = '';
    const statusIcon = optimizationStatusSection.querySelector('.status-icon');
    if (statusIcon) {
      statusIcon.style.display = '';
    }
    
    // 重置进度条
    updateOptimizationProgress(0);
    
    // 隐藏结果区域
    optimizationResultSection.style.display = 'none';
    optimizationProgressContainer.style.display = 'none';
    
    // 隐藏整个状态区域
    optimizationStatusSection.style.display = 'none';
    
    // 重置按钮状态
    setOptimizationLoading(false);
  }

  function showDubbingResult(resultUrl) {
    const fileName = resultUrl.split('/').pop();
    
    // 添加CSS类来隐藏状态内容
    dubbingStatusSection.classList.add('show-result');
    
    // 设置下载链接
    dubbingDownloadLink.href = resultUrl;
    dubbingDownloadLink.download = fileName;
    
    // 显示结果区域，隐藏进度条
    dubbingResultSection.style.display = 'block';
    dubbingProgressContainer.style.display = 'none';
    
    // Add success animation
    dubbingResultSection.classList.add('success-animation');
    setTimeout(() => {
      dubbingResultSection.classList.remove('success-animation');
    }, 600);
  }

  function cleanupDubbingTask() {
    // 清理之前的轮询interval
    if (currentTaskInterval) {
      clearInterval(currentTaskInterval);
      currentTaskInterval = null;
    }
    
    // 移除结果显示类
    dubbingStatusSection.classList.remove('show-result');
    
    // 重置状态界面元素的显示状态
    dubbingStatusTitle.style.display = '';
    dubbingStatusMessage.style.display = '';
    const statusIcon = dubbingStatusSection.querySelector('.status-icon');
    if (statusIcon) {
      statusIcon.style.display = '';
    }
    
    // 重置进度条
    updateDubbingProgress(0);
    
    // 隐藏结果区域
    dubbingResultSection.style.display = 'none';
    dubbingProgressContainer.style.display = 'none';
    
    // 隐藏整个状态区域
    dubbingStatusSection.style.display = 'none';
    
    // 重置按钮状态
    setFormLoading(false);
  }

  function showOptimizationError(message) {
    showOptimizationStatus('优化失败', message);
    optimizationProgressContainer.style.display = 'none';
    
    // Show error in optimization status section
    optimizationStatusSection.style.display = 'block';
    
    // Auto-hide after 8 seconds
    setTimeout(() => {
      if (optimizationStatusTitle.textContent === '优化失败') {
        optimizationStatusSection.style.display = 'none';
      }
    }, 8000);
  }

  initApp();
});

// Add shake animation and error styles via CSS
const style = document.createElement('style');
style.textContent = `
  @keyframes shake {
    0%, 100% { transform: translateX(0); }
    25% { transform: translateX(-5px); }
    75% { transform: translateX(5px); }
  }
  
  .error-field {
    border-color: #ef4444 !important;
    box-shadow: 0 0 0 3px rgba(239, 68, 68, 0.1) !important;
  }
`;
document.head.appendChild(style);

// IndexTTS2 Emotion Control Functions
function setupIndexTTS2Controls() {
  const engineSelect = document.getElementById('tts_engine');
  const emotionModeSelect = document.getElementById('emotion_mode');
  const emotionAlphaSlider = document.getElementById('emotion_alpha');
  const emotionAlphaValue = document.getElementById('emotion-alpha-value');

  if (!engineSelect) {
    console.error('TTS引擎选择器未找到');
    return;
  }

  // 监听TTS引擎变化
  engineSelect.addEventListener('change', function() {
    toggleEmotionControls(this.value);
  });

  // 监听情感模式变化
  if (emotionModeSelect) {
    emotionModeSelect.addEventListener('change', function() {
      toggleEmotionSections(this.value);
    });
  }

  // 监听情感强度滑块变化
  if (emotionAlphaSlider && emotionAlphaValue) {
    emotionAlphaSlider.addEventListener('input', function() {
      emotionAlphaValue.textContent = this.value;
    });
  }

  // 初始化时检查当前引擎
  toggleEmotionControls(engineSelect.value);
  if (emotionModeSelect) {
    toggleEmotionSections(emotionModeSelect.value);
  }
}

function toggleEmotionControls(engineValue) {
  const emotionTab = document.getElementById('tab-emotion-btn');
  const emotionTabContent = document.getElementById('tab-emotion');
  
  if (engineValue === 'index_tts2') {
    // 显示IndexTTS2情感控制标签页
    if (emotionTab) {
      emotionTab.style.setProperty('display', 'inline-block', 'important');
      emotionTab.style.setProperty('visibility', 'visible', 'important');
      emotionTab.style.setProperty('opacity', '1', 'important');
      
      // 移除任何可能覆盖默认样式的强制样式
      emotionTab.style.removeProperty('background-color');
      emotionTab.style.removeProperty('color');
      emotionTab.style.removeProperty('border');
      emotionTab.style.removeProperty('border-radius');
      emotionTab.style.removeProperty('padding');
      emotionTab.style.removeProperty('margin-left');
      emotionTab.style.removeProperty('font-weight');
      emotionTab.style.removeProperty('cursor');
      emotionTab.style.removeProperty('transition');
      
      // 移除可能的hidden类
      emotionTab.classList.remove('hidden');
    }
  } else {
    // 隐藏IndexTTS2情感控制标签页
    if (emotionTab) {
      emotionTab.style.setProperty('display', 'none', 'important');
    }
    if (emotionTabContent) {
      emotionTabContent.style.setProperty('display', 'none', 'important');
    }
    
    // 如果当前在情感控制标签页，切换到并发配置标签页
    if (emotionTabContent.style.display !== 'none') {
      const concurrencyTab = document.querySelector('[data-tab="tab-concurrency"]');
      const concurrencyTabContent = document.getElementById('tab-concurrency');
      
      // 切换标签页状态
      document.querySelectorAll('.tab-link').forEach(tab => tab.classList.remove('active'));
      document.querySelectorAll('.tab-content').forEach(content => content.style.display = 'none');
      
      concurrencyTab.classList.add('active');
      concurrencyTabContent.style.display = 'block';
    }
    
    // 重置情感控制参数为默认值
    resetEmotionControls();
  }
}

function toggleEmotionSections(emotionMode) {
  // 隐藏所有情感配置区域
  const emotionSections = document.querySelectorAll('.emotion-section');
  emotionSections.forEach(section => {
    section.style.display = 'none';
  });

  // 根据模式显示对应的配置区域
  switch(emotionMode) {
    case 'audio':
      document.getElementById('emotion-audio-section').style.display = 'block';
      break;
    case 'vector':
      document.getElementById('emotion-vector-section').style.display = 'block';
      break;
    case 'text':
      document.getElementById('emotion-text-section').style.display = 'block';
      break;
    case 'auto':
      // 自动模式不需要额外配置
      break;
  }
}

function resetEmotionControls() {
  // 重置所有情感控制参数为默认值
  document.getElementById('emotion_mode').value = 'auto';
  document.getElementById('emotion_audio_file').value = '';
  document.getElementById('emotion_vector').value = '';
  document.getElementById('emotion_text').value = '';
  document.getElementById('emotion_alpha').value = '0.8';
  document.getElementById('emotion-alpha-value').textContent = '0.8';
  document.getElementById('use_random').checked = false;
  
  // 隐藏所有情感配置区域
  toggleEmotionSections('auto');
}