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

  // File upload areas
  const uploadAreas = document.querySelectorAll('.file-upload-area');
  const fileInputs = document.querySelectorAll('.file-input');

  // NEW: Reference Audio Selection
  const referenceAudioSelect = document.getElementById('reference-audio-select');
  const voicePairsContainer = document.getElementById('voice-pairs-container');
  let builtInAudios = {};
  let currentTaskInterval = null;

  document.addEventListener('click', (e) => {
    if (e.target.closest('.file-upload-area') && e.target.tagName !== 'INPUT') {
      const uploadArea = e.target.closest('.file-upload-area');
      const input = uploadArea.querySelector('.file-input');
      if (input) {
        input.click();
      }
    }
  });

  // MODIFIED: Voice pair management - now more flexible
  function createVoicePair({ isCustom = false, name = '', path = '', text = '' } = {}) {
    voicePairsContainer.innerHTML = ''; // Clear previous pair
    const pairDiv = document.createElement('div');
    pairDiv.classList.add('voice-pair');

    if (isCustom) {
      pairDiv.innerHTML = `
        <div class="file-upload-area" data-type="voice">
          <input type="file" name="voice_files" accept=".wav,.mp3" required class="file-input">
          <div class="upload-content">
            <i class="fas fa-cloud-upload-alt"></i>
            <p>选择语音文件</p>
            <span class="file-name">未选择</span>
          </div>
        </div>
        <textarea name="prompt_texts" placeholder="输入参考文本..." class="form-textarea" required></textarea>
        <button type="button" class="remove-pair-btn"><i class="fas fa-trash"></i></button>
      `;
      const input = pairDiv.querySelector('.file-input');
      const uploadArea = pairDiv.querySelector('.file-upload-area');
      input.addEventListener('change', (e) => handleFileSelection(e, uploadArea, 'voice'));
    } else {
      pairDiv.dataset.path = path;
      pairDiv.innerHTML = `
        <div class="file-upload-area preset" data-type="voice">
          <div class="upload-content">
            <i class="fas fa-check-circle" style="color: #10b981;"></i>
            <p>内置音频: <strong>${name}</strong></p>
            <span class="file-name" style="color: #10b981;">${path}</span>
          </div>
        </div>
        <textarea name="prompt_texts" placeholder="输入参考文本..." class="form-textarea" required>${text}</textarea>
        <button type="button" class="remove-pair-btn"><i class="fas fa-trash"></i></button>
      `;
    }

    const removeBtn = pairDiv.querySelector('.remove-pair-btn');
    removeBtn.addEventListener('click', () => {
        pairDiv.remove();
        // Reset dropdown to prevent inconsistent state
        if(referenceAudioSelect) referenceAudioSelect.value = 'custom_upload';
    });

    voicePairsContainer.appendChild(pairDiv);
  }

  // Initialize the application
  initApp();

  // MODIFIED: initApp to load built-in audios and set up new controls
  async function initApp() {
    await loadOptions();
    await loadConfig();
    await loadBuiltInAudios(); // NEW

    setupFileUploads();
    setupFormSubmission();
    setupOptimizationForm();
    setupFormValidation();
    setupTabs();
    setupIndexTTS2Controls();
    setupMainTabs();
    setupPasswordToggle();
  }

  // NEW: Load built-in audios from the new endpoint
  async function loadBuiltInAudios() {
    try {
        const response = await fetch('/dubbing/built-in-audios');
        if (!response.ok) {
            throw new Error(`HTTP ${response.status}: ${response.statusText}`);
        }
        builtInAudios = await response.json();
        populateReferenceAudioSelector();
    } catch (error) {
        console.error('Failed to load built-in audios:', error);
        showError('加载内置音频列表失败');
        populateReferenceAudioSelector(); // Populate with only custom option
    }
  }

  // NEW: Populate the reference audio dropdown
  function populateReferenceAudioSelector() {
    referenceAudioSelect.innerHTML = '';

    const audioNames = Object.keys(builtInAudios);
    if (audioNames.length > 0) {
      audioNames.forEach(name => {
        const option = document.createElement('option');
        option.value = name;
        option.textContent = name;
        referenceAudioSelect.appendChild(option);
      });
    }

    const customOption = document.createElement('option');
    customOption.value = 'custom_upload';
    customOption.textContent = '上传自定义音频';
    referenceAudioSelect.appendChild(customOption);

    referenceAudioSelect.addEventListener('change', handleReferenceAudioChange);

    // Set initial state
    if (audioNames.length > 0) {
      referenceAudioSelect.value = audioNames[0];
    } else {
      referenceAudioSelect.value = 'custom_upload';
    }
    handleReferenceAudioChange(); // Trigger change to show initial UI
  }

  // NEW: Handle dropdown change
  function handleReferenceAudioChange() {
    const selectedValue = referenceAudioSelect.value;
    if (selectedValue === 'custom_upload') {
      createVoicePair({ isCustom: true });
    } else {
      const audioData = builtInAudios[selectedValue];
      createVoicePair({
        isCustom: false,
        name: selectedValue,
        path: audioData.path,
        text: audioData.text
      });
    }
  }

  function setupPasswordToggle() {
    document.addEventListener('click', e => {
      if (e.target.classList.contains('toggle-password')) {
        const icon = e.target;
        const input = icon.previousElementSibling;
        if (input && input.tagName === 'INPUT') {
          if (input.type === 'password') {
            input.type = 'text';
            icon.classList.remove('fa-eye');
            icon.classList.add('fa-eye-slash');
          } else {
            input.type = 'password';
            icon.classList.remove('fa-eye-slash');
            icon.classList.add('fa-eye');
          }
        }
      }
    });
  }

  // Load options from server
  async function loadOptions() {
    try {
      showLoadingState();
      const response = await fetch('/dubbing/options');
      
      if (!response.ok) {
        throw new Error(`HTTP ${response.status}: ${response.statusText}`);
      }
      
      const data = await response.json();
      
      populateSelect(engineSelect, data.tts_engines || [], 'TTS 引擎', 'fish_speech');
      populateSelect(strategySelect, data.strategies || [], '策略', 'stretch');
      populateSelect(languageSelect, data.languages || [], '语言');
      
      hideLoadingState();
    } catch (error) {
      console.error('Failed to load options:', error);
      showError('加载配置选项失败，请刷新页面重试');
      hideLoadingState();
    }
  }

  function showLoadingState() {
    [engineSelect, strategySelect, languageSelect].forEach(select => {
      select.innerHTML = '<option value="">加载中...</option>';
      select.disabled = true;
    });
  }

  function hideLoadingState() {
    [engineSelect, strategySelect, languageSelect].forEach(select => {
      select.disabled = false;
    });
  }

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
      if (option === defaultValue) {
        opt.selected = true;
      }
      select.appendChild(opt);
    });
  }

  function setupTabs() {
    const tabLinks = document.querySelectorAll('.tab-link');
    const tabContents = document.querySelectorAll('.tab-content');

    tabLinks.forEach(link => {
      link.addEventListener('click', () => {
        const tabId = link.dataset.tab;
        tabLinks.forEach(l => l.classList.remove('active'));
        tabContents.forEach(c => {
          c.classList.remove('active');
          c.style.display = 'none';
        });
        link.classList.add('active');
        const targetContent = document.getElementById(tabId);
        if (targetContent) {
          targetContent.classList.add('active');
          targetContent.style.display = 'block';
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
        mainTabLinks.forEach(l => l.classList.remove('active'));
        mainTabContents.forEach(c => c.classList.remove('active'));
        link.classList.add('active');
        const targetTab = document.getElementById(tabId);
        if (targetTab) {
          targetTab.classList.add('active');
        }
      });
    });
  }

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
      
      if (data.basic) {
        setConfigFieldValue('#tts_engine', data.basic.tts_engine);
        setConfigFieldValue('#strategy', data.basic.strategy);
      }

      if (data.time_borrowing) {
          setTimeout(() => {
          setConfigFieldValue('input[name="opt_min_gap_threshold"]', data.time_borrowing.min_gap_threshold);
          setConfigFieldValue('input[name="opt_borrow_ratio"]', data.time_borrowing.borrow_ratio);
          setConfigFieldValue('input[name="opt_extra_buffer"]', data.time_borrowing.extra_buffer);
          }, 100);
      }

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

  function setupInputMode() {
    const inputModeRadios = document.querySelectorAll('input[name="input_mode"]');
    const fileUploadSection = document.getElementById('file-upload-section');
    const textInputSection = document.getElementById('text-input-section');
    
    inputModeRadios.forEach(radio => {
      radio.addEventListener('change', function() {
        if (this.value === 'file') {
          fileUploadSection.style.display = 'block';
          textInputSection.style.display = 'none';
          const fileInput = document.querySelector('input[name="input_file"]');
          if (fileInput) fileInput.required = true;
          const textInput = document.querySelector('textarea[name="input_text"]');
          if (textInput) textInput.required = false;
        } else if (this.value === 'text') {
          fileUploadSection.style.display = 'none';
          textInputSection.style.display = 'block';
          const textInput = document.querySelector('textarea[name="input_text"]');
          if (textInput) textInput.required = true;
          const fileInput = document.querySelector('input[name="input_file"]');
          if (fileInput) fileInput.required = false;
        }
      });
    });
  }
  
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

  function setupFileUploads() {
    // This function is now only for the main SRT/TXT upload
    const mainUploadArea = document.querySelector('#file-upload-section .file-upload-area');
    const mainInput = document.querySelector('input[name="input_file"]');
    
    if (mainUploadArea && mainInput) {
        mainInput.addEventListener('change', (e) => handleFileSelection(e, mainUploadArea, 'srt'));
        mainUploadArea.addEventListener('dragover', handleDragOver);
        mainUploadArea.addEventListener('dragleave', handleDragLeave);
        mainUploadArea.addEventListener('drop', (e) => handleDrop(e, mainUploadArea, mainInput, 'srt'));
        mainUploadArea.addEventListener('dragenter', (e) => e.preventDefault());
    }
    
    setupInputMode();
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
      fileNameSpan.textContent = files[0].name;
      fileNameSpan.style.color = '#10b981';
      uploadContent.innerHTML = `
        <i class="fas fa-check-circle" style="color: #10b981;"></i>
        <p>文件已选择</p>
        <span class="file-name" style="color: #10b981;">${fileNameSpan.textContent}</span>
      `;
    } else {
      fileNameSpan.textContent = '未选择文件';
      fileNameSpan.style.color = '#999';
      uploadContent.innerHTML = `
        <i class="fas fa-cloud-upload-alt"></i>
        <p>点击选择文件或拖拽到此处</p>
        <span class="file-name">未选择文件</span>
      `;
    }
  }

  function setupFormValidation() {
    // Validation will now only run on submit
  }

  function setupFormSubmission() {
    form.addEventListener('submit', handleFormSubmit);
  }

  function setupOptimizationForm() {
    if (optimizationForm) {
      optimizationForm.addEventListener('submit', handleOptimizationSubmit);
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
    const file = optimizationFile.files[0];
    if (!file.name.toLowerCase().endsWith('.srt')) {
      showError('仅支持 .srt 格式的字幕文件');
      return;
    }
    cleanupOptimizationTask();
    showOptimizationStatus('准备中...', '正在保存配置并准备字幕优化...');
    optimizationStatusSection.style.display = 'block';
    setOptimizationLoading(true);
    try {
      const configData = getFormConfig();
      await fetch('/dubbing/config', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(configData),
      });
      showOptimizationStatus('准备中...', '配置已保存，正在开始字幕优化...');
      const formData = new FormData();
      formData.append('input_file', file);
      const response = await fetch('/subtitle-optimization', { method: 'POST', body: formData });
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

  async function handleFormSubmit(e) {
    e.preventDefault();
    if (!validateForm()) return;
    cleanupDubbingTask();
    showDubbingStatus('准备中...', '正在保存配置...');
    dubbingStatusSection.style.display = 'block';
    setFormLoading(true);
    
    try {
      const configData = getFormConfig();
      await fetch('/dubbing/config', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(configData)
      }).then(res => {
          if(res.ok) showDubbingStatus('准备中...', '配置已保存，正在准备文件上传...');
          else console.warn('配置保存失败，但继续执行配音任务');
      }).catch(err => console.warn('配置保存出错:', err));

      const formData = new FormData();
      const fieldsToAppend = ['tts_engine', 'strategy', 'language'];
      fieldsToAppend.forEach(id => formData.append(id, document.getElementById(id).value));

      const inputMode = document.querySelector('input[name="input_mode"]:checked').value;
      formData.append('input_mode', inputMode);
      if (inputMode === 'file') {
        const inputFile = document.querySelector('input[name="input_file"]');
        if(inputFile.files.length > 0) formData.append('input_file', inputFile.files[0]);
      } else if (inputMode === 'text') {
        formData.append('input_text', document.querySelector('textarea[name="input_text"]').value);
        formData.append('text_format', document.querySelector('input[name="text_format"]:checked').value);
      }

      const configInputs = document.querySelectorAll('#tab-concurrency input');
      configInputs.forEach(input => formData.append(input.name, input.value));

      if (document.getElementById('tts_engine').value === 'index_tts2') {
        formData.append('emotion_mode', document.getElementById('emotion_mode').value);
        const emotionAudioFile = document.getElementById('emotion_audio_file');
        if (emotionAudioFile && emotionAudioFile.files.length > 0) formData.append('emotion_audio_file', emotionAudioFile.files[0]);
        if (document.getElementById('emotion_vector').value.trim()) formData.append('emotion_vector', document.getElementById('emotion_vector').value.trim());
        if (document.getElementById('emotion_text').value.trim()) formData.append('emotion_text', document.getElementById('emotion_text').value.trim());
        formData.append('emotion_alpha', document.getElementById('emotion_alpha').value);
        formData.append('use_random', document.getElementById('use_random').checked);
      }

      const voicePairs = document.querySelectorAll('.voice-pair');
      voicePairs.forEach(pair => {
        const fileInput = pair.querySelector('input[type="file"]');
        const promptText = pair.querySelector('textarea').value;
        const originalPath = pair.dataset.path || '';
        if ((fileInput && fileInput.files.length > 0 || originalPath) && promptText) {
            if (fileInput && fileInput.files.length > 0) {
                formData.append('voice_files', fileInput.files[0]);
                formData.append('voice_files_paths', '');
            } else if (originalPath) {
                formData.append('voice_files', new Blob(), '');
                formData.append('voice_files_paths', originalPath);
            }
            formData.append('prompt_texts', promptText);
        }
      });

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
      setFormLoading(false);
    }
  }

  async function pollTaskStatus(taskId, taskType = 'dubbing') {
    if (taskType === 'optimization') showOptimizationProgress();
    else showDubbingProgress();
    
    const statusUrl = taskType === 'optimization' ? `/subtitle-optimization/status/${taskId}` : `/dubbing/status/${taskId}`;
    
    const checkStatus = async () => {
      try {
        const response = await fetch(statusUrl);
        if (!response.ok) throw new Error('无法获取任务状态');
        const data = await response.json();
        
        if (taskType === 'optimization') {
          optimizationStatusMessage.textContent = data.message || `当前进度: ${data.progress}%`;
          updateOptimizationProgress(data.progress);
        } else {
          dubbingStatusMessage.textContent = data.message || `当前进度: ${data.progress}%`;
          updateDubbingProgress(data.progress);
        }
        
        if (data.status === 'completed') {
          if (currentTaskInterval) clearInterval(currentTaskInterval);
          currentTaskInterval = null;
          if (taskType === 'optimization') {
            showOptimizationResult(data.result_url);
            setOptimizationLoading(false);
          } else {
            showDubbingResult(data.result_url);
            setFormLoading(false);
          }
          return true;
        } else if (data.status === 'failed') {
          if (currentTaskInterval) clearInterval(currentTaskInterval);
          currentTaskInterval = null;
          if (taskType === 'optimization') {
            showOptimizationError(`字幕优化失败: ${data.error || '未知错误'}`);
            setOptimizationLoading(false);
          } else {
            showDubbingError(`配音失败: ${data.error || '未知错误'}`);
            setFormLoading(false);
          }
          return true;
        }
        return false;
      } catch (error) {
        console.error('Polling error:', error);
        if (currentTaskInterval) clearInterval(currentTaskInterval);
        currentTaskInterval = null;
        if (taskType === 'optimization') {
          showOptimizationError('无法轮询任务状态');
          setOptimizationLoading(false);
        } else {
          showDubbingError('无法轮询任务状态');
          setFormLoading(false);
        }
        return true;
      }
    };
    
    if (await checkStatus()) return;
    currentTaskInterval = setInterval(async () => {
      if (await checkStatus()) {
        if (currentTaskInterval) clearInterval(currentTaskInterval);
        currentTaskInterval = null;
      }
    }, 500);
  }

  function validateForm() {
    let isValid = true;
    form.querySelectorAll('.error-field').forEach(field => field.classList.remove('error-field'));
    
    const inputMode = document.querySelector('input[name="input_mode"]:checked').value;
    if (inputMode === 'file') {
      const fileInput = document.querySelector('input[name="input_file"]');
      if (fileInput.files.length === 0) {
        isValid = false;
        fileInput.closest('.file-upload-area').classList.add('error-field');
      }
    } else if (inputMode === 'text') {
      const textInput = document.querySelector('textarea[name="input_text"]');
      if (!textInput.value.trim()) {
        isValid = false;
        textInput.classList.add('error-field');
      }
    }
    
    // Validate that at least one voice pair with prompt text is present
    const voicePairs = document.querySelectorAll('.voice-pair');
    if (voicePairs.length === 0) {
        isValid = false;
    } else {
        let hasValidPair = false;
        voicePairs.forEach(pair => {
            const promptText = pair.querySelector('textarea[name="prompt_texts"]');
            if (promptText && promptText.value.trim() !== '') {
                hasValidPair = true;
            } else {
                promptText.classList.add('error-field');
            }
        });
        if (!hasValidPair) isValid = false;
    }
    
    if (!isValid) showError('请填写所有必填字段，并确保参考音频有对应的文本。');
    return isValid;
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
    dubbingStatusSection.classList.remove('show-result');
  }

  function showDubbingProgress() {
    showDubbingStatus('配音处理中...', '正在处理配音...');
    dubbingProgressContainer.style.display = 'block';
  }

  function updateDubbingProgress(progress) {
    dubbingProgressFill.style.width = `${progress}%`;
    dubbingProgressText.textContent = `${Math.round(progress)}%`;
  }

  function showDubbingResult(resultUrl) {
    dubbingStatusSection.classList.add('show-result');
    dubbingDownloadLink.href = resultUrl;
    dubbingDownloadLink.download = resultUrl.split('/').pop();
    dubbingResultSection.style.display = 'block';
    dubbingProgressContainer.style.display = 'none';
    dubbingResultSection.classList.add('success-animation');
  }

  function cleanupDubbingTask() {
    if (currentTaskInterval) clearInterval(currentTaskInterval);
    currentTaskInterval = null;
    dubbingStatusSection.style.display = 'none';
    setFormLoading(false);
  }

  function showDubbingError(message) {
    showDubbingStatus('配音失败', message);
    setTimeout(() => {
      if (dubbingStatusTitle.textContent === '配音失败') {
        dubbingStatusSection.style.display = 'none';
      }
    }, 8000);
  }

  function showOptimizationStatus(title, message) {
    optimizationStatusTitle.textContent = title;
    optimizationStatusMessage.textContent = message;
    optimizationProgressContainer.style.display = 'none';
    optimizationResultSection.style.display = 'none';
    optimizationStatusSection.classList.remove('show-result');
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
    optimizationStatusSection.classList.add('show-result');
    optimizationDownloadLink.href = resultUrl;
    optimizationDownloadLink.download = resultUrl.split('/').pop();
    optimizationResultSection.style.display = 'block';
    optimizationProgressContainer.style.display = 'none';
    optimizationResultSection.classList.add('success-animation');
  }

  function cleanupOptimizationTask() {
    if (currentTaskInterval) clearInterval(currentTaskInterval);
    currentTaskInterval = null;
    optimizationStatusSection.style.display = 'none';
    setOptimizationLoading(false);
  }

  function showOptimizationError(message) {
    showOptimizationStatus('优化失败', message);
    setTimeout(() => {
      if (optimizationStatusTitle.textContent === '优化失败') {
        optimizationStatusSection.style.display = 'none';
      }
    }, 8000);
  }

  function showError(message) {
    // A generic error display, maybe repurpose one of the status bars
    showDubbingError(message);
  }
});

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

function setupIndexTTS2Controls() {
  const engineSelect = document.getElementById('tts_engine');
  const emotionModeSelect = document.getElementById('emotion_mode');
  const emotionAlphaSlider = document.getElementById('emotion_alpha');
  const emotionAlphaValue = document.getElementById('emotion-alpha-value');

  if (!engineSelect) return;

  engineSelect.addEventListener('change', () => toggleEmotionControls(engineSelect.value));
  if (emotionModeSelect) emotionModeSelect.addEventListener('change', () => toggleEmotionSections(emotionModeSelect.value));
  if (emotionAlphaSlider) emotionAlphaSlider.addEventListener('input', () => emotionAlphaValue.textContent = emotionAlphaSlider.value);

  toggleEmotionControls(engineSelect.value);
  if (emotionModeSelect) toggleEmotionSections(emotionModeSelect.value);
}

function toggleEmotionControls(engineValue) {
  const emotionTab = document.getElementById('tab-emotion-btn');
  const emotionTabContent = document.getElementById('tab-emotion');
  if (engineValue === 'index_tts2') {
    if (emotionTab) emotionTab.style.display = 'inline-block';
  } else {
    if (emotionTab) emotionTab.style.display = 'none';
    if (emotionTabContent && emotionTabContent.classList.contains('active')) {
      document.querySelector('[data-tab="tab-concurrency"]').click();
    }
    resetEmotionControls();
  }
}

function toggleEmotionSections(emotionMode) {
  document.querySelectorAll('.emotion-section').forEach(section => section.style.display = 'none');
  const section = document.getElementById(`emotion-${emotionMode}-section`);
  if (section) section.style.display = 'block';
}

function resetEmotionControls() {
  document.getElementById('emotion_mode').value = 'auto';
  document.getElementById('emotion_audio_file').value = '';
  document.getElementById('emotion_vector').value = '';
  document.getElementById('emotion_text').value = '';
  document.getElementById('emotion_alpha').value = '0.8';
  document.getElementById('emotion-alpha-value').textContent = '0.8';
  document.getElementById('use_random').checked = false;
  toggleEmotionSections('auto');
}