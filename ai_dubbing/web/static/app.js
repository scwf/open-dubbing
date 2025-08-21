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
  
  const engineSelect = document.getElementById('tts_engine');
  const strategySelect = document.getElementById('strategy');
  const languageSelect = document.getElementById('language');

  // File upload areas
  const uploadAreas = document.querySelectorAll('.file-upload-area');
  const fileInputs = document.querySelectorAll('.file-input');

  document.addEventListener('click', (e) => {
    if (e.target.closest('.file-upload-area') && e.target.tagName !== 'INPUT') {
      const uploadArea = e.target.closest('.file-upload-area');
      const input = uploadArea.querySelector('.file-input');
      if (input) {
        input.click();
      }
    }
  });

  // Voice pair management
  const voicePairsContainer = document.getElementById('voice-pairs-container');
  const addVoicePairBtn = document.getElementById('add-voice-pair-btn');
  let pairCount = 0;

  function createVoicePair() {
    pairCount++;
    const pairDiv = document.createElement('div');
    pairDiv.classList.add('voice-pair');
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
    
    const removeBtn = pairDiv.querySelector('.remove-pair-btn');
    removeBtn.addEventListener('click', () => {
      pairDiv.remove();
    });

    voicePairsContainer.appendChild(pairDiv);
  }

  addVoicePairBtn.addEventListener('click', createVoicePair);
  createVoicePair(); // Add the first pair initially

  // Initialize the application
  initApp();

  async function initApp() {
    await loadOptions();
    const basicConfig = await loadConfig();
    setupFileUploads();
    setupFormSubmission();
    setupFormValidation();
    setupConfigSaving();
    setupTabs();
    setupPasswordToggle();
    
    // Populate voice pairs with config data if available
    if (basicConfig && basicConfig.voice_files && basicConfig.prompt_texts) {
      populateVoicePairsFromConfig(basicConfig);
    }
  }

  function populateVoicePairsFromConfig(basicConfig) {
    try {
      // Clear existing voice pairs
      voicePairsContainer.innerHTML = '';
      
      // Parse voice files and prompt texts from config
      const voiceFiles = basicConfig.voice_files.split(',').map(file => file.trim());
      const promptTexts = basicConfig.prompt_texts.split(',').map(text => text.trim());
      
      // Create voice pairs for each config entry
      for (let i = 0; i < voiceFiles.length; i++) {
        if (i >= promptTexts.length) break;
        
        const pairDiv = document.createElement('div');
        pairDiv.classList.add('voice-pair');
        pairDiv.innerHTML = `
          <div class="file-upload-area" data-type="voice">
            <input type="file" name="voice_files" accept=".wav,.mp3" required class="file-input">
            <div class="upload-content">
              <i class="fas fa-cloud-upload-alt"></i>
              <p>选择语音文件</p>
              <span class="file-name">${voiceFiles[i]}</span>
            </div>
          </div>
          <textarea name="prompt_texts" placeholder="输入参考文本..." class="form-textarea" required>${promptTexts[i]}</textarea>
          <button type="button" class="remove-pair-btn"><i class="fas fa-trash"></i></button>
        `;

        const input = pairDiv.querySelector('.file-input');
        const uploadArea = pairDiv.querySelector('.file-upload-area');
        
        input.addEventListener('change', (e) => handleFileSelection(e, uploadArea, 'voice'));
        
        const removeBtn = pairDiv.querySelector('.remove-pair-btn');
        removeBtn.addEventListener('click', () => {
          pairDiv.remove();
        });

        voicePairsContainer.appendChild(pairDiv);
      }
    } catch (error) {
      console.error('Failed to populate voice pairs from config:', error);
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
    
    // Add placeholder option
    const placeholderOpt = document.createElement('option');
    placeholderOpt.value = '';
    placeholderOpt.textContent = `选择${placeholder}`;
    placeholderOpt.disabled = true;
    select.appendChild(placeholderOpt);
    
    // Add options
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
        tabContents.forEach(c => c.classList.remove('active'));

        link.classList.add('active');
        document.getElementById(tabId).classList.add('active');
      });
    });
  }
async function loadConfig() {
    try {
      const response = await fetch('/dubbing/config');
      const data = await response.json();
      
      // Set basic configuration values
      if (data.basic) {
        if (data.basic.tts_engine) {
          document.getElementById('tts_engine').value = data.basic.tts_engine;
        }
        if (data.basic.strategy) {
          document.getElementById('strategy').value = data.basic.strategy;
        }
        if (data.basic.language) {
          document.getElementById('language').value = data.basic.language;
        }
      }
      
      const concurrencyTab = document.getElementById('tab-concurrency');
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

      const subtitleTab = document.getElementById('tab-subtitle');
      subtitleTab.innerHTML = `
        <div class="options-row">
          <div class="form-group">
            <label class="form-label">LLM API Key</label>
            <div class="password-input-container">
              <input type="password" name="llm_api_key" class="form-select" value="${data.subtitle_optimization.llm_api_key}">
              <i class="fas fa-eye toggle-password"></i>
            </div>
          </div>
          <div class="form-group">
            <label class="form-label">LLM Model</label>
            <input type="text" name="llm_model" class="form-select" value="${data.subtitle_optimization.llm_model}">
          </div>
          <div class="form-group">
            <label class="form-label">Base URL</label>
            <input type="text" name="base_url" class="form-select" value="${data.subtitle_optimization.base_url}">
          </div>
          <div class="form-group">
            <label class="form-label">中文最小字符时间 (ms)</label>
            <input type="number" name="chinese_char_min_time" class="form-select" value="${data.subtitle_optimization.chinese_char_min_time}">
          </div>
          <div class="form-group">
            <label class="form-label">英文最小单词时间 (ms)</label>
            <input type="number" name="english_word_min_time" class="form-select" value="${data.subtitle_optimization.english_word_min_time}">
          </div>
          <div class="form-group">
            <label class="form-label">LLM最大并发数</label>
            <input type="number" name="llm_max_concurrency" class="form-select" value="${data.subtitle_optimization.llm_max_concurrency}">
          </div>
          <div class="form-group">
            <label class="form-label">LLM最大重试次数</label>
            <input type="number" name="llm_max_retries" class="form-select" value="${data.subtitle_optimization.llm_max_retries}">
          </div>
          <div class="form-group">
            <label class="form-label">LLM超时 (s)</label>
            <input type="number" name="llm_timeout" class="form-select" value="${data.subtitle_optimization.llm_timeout}">
          </div>
          <div class="form-group">
            <label class="form-label">优化后SRT输出目录</label>
            <input type="text" name="optimized_srt_output_file" class="form-select" value="${data.subtitle_optimization.optimized_srt_output_file}">
          </div>
        </div>
      `;

      const timeTab = document.getElementById('tab-time');
      timeTab.innerHTML = `
        <div class="options-row">
          <div class="form-group">
            <label class="form-label">最小保护空隙 (ms)</label>
            <input type="number" name="min_gap_threshold" class="form-select" value="${data.time_borrowing.min_gap_threshold}">
          </div>
          <div class="form-group">
            <label class="form-label">借用比例</label>
            <input type="number" step="0.1" name="borrow_ratio" class="form-select" value="${data.time_borrowing.borrow_ratio}">
          </div>
          <div class="form-group">
            <label class="form-label">额外缓冲时间 (ms)</label>
            <input type="number" name="extra_buffer" class="form-select" value="${data.time_borrowing.extra_buffer}">
          </div>
        </div>
      `;

      return data.basic;
    } catch (error) {
      console.error('Failed to load config:', error);
      return null;
    }
  }

  function setupConfigSaving() {
    const saveBtn = document.getElementById('save-config-btn');
    saveBtn.addEventListener('click', async () => {
      const configData = {
        concurrency: {
          tts_max_concurrency: document.querySelector('[name="tts_max_concurrency"]').value,
          tts_max_retries: document.querySelector('[name="tts_max_retries"]').value,
        },
        subtitle_optimization: {
          llm_api_key: document.querySelector('[name="llm_api_key"]').value,
          llm_model: document.querySelector('[name="llm_model"]').value,
          base_url: document.querySelector('[name="base_url"]').value,
          chinese_char_min_time: document.querySelector('[name="chinese_char_min_time"]').value,
          english_word_min_time: document.querySelector('[name="english_word_min_time"]').value,
          llm_max_concurrency: document.querySelector('[name="llm_max_concurrency"]').value,
          llm_max_retries: document.querySelector('[name="llm_max_retries"]').value,
          llm_timeout: document.querySelector('[name="llm_timeout"]').value,
          optimized_srt_output_file: document.querySelector('[name="optimized_srt_output_file"]').value,
        },
        time_borrowing: {
          min_gap_threshold: document.querySelector('[name="min_gap_threshold"]').value,
          borrow_ratio: document.querySelector('[name="borrow_ratio"]').value,
          extra_buffer: document.querySelector('[name="extra_buffer"]').value,
        }
      };
      
      try {
        await fetch('/dubbing/config', {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
          },
          body: JSON.stringify(configData),
        });
        alert('配置已保存！');
      } catch (error) {
        console.error('Failed to save config:', error);
        alert('配置保存失败！');
      }
    });
  }

  // Setup file upload functionality
  function setupFileUploads() {
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

  async function handleFormSubmit(e) {
    e.preventDefault();
    
    if (!validateForm()) {
      return;
    }

    showStatus('准备中...', '正在准备文件上传...');
    statusSection.style.display = 'block';
    setFormLoading(true);
    
    try {
      const formData = new FormData(form);
      const response = await fetch('/dubbing', {
        method: 'POST',
        body: formData
      });
      
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
      showError(`处理失败: ${error.message}`);
      setFormLoading(false);
    }
  }

  async function pollTaskStatus(taskId) {
    showProgress();
    const interval = setInterval(async () => {
      try {
        const response = await fetch(`/dubbing/status/${taskId}`);
        if (!response.ok) {
          throw new Error('无法获取任务状态');
        }
        
        const data = await response.json();
        
        statusTitle.textContent = "处理中...";
        statusMessage.textContent = data.message || `当前进度: ${data.progress}%`;
        updateProgress(data.progress);
        
        if (data.status === 'completed') {
          clearInterval(interval);
          showResult(data.result_url);
          setFormLoading(false);
        } else if (data.status === 'failed') {
          clearInterval(interval);
          showError(`处理失败: ${data.error || '未知错误'}`);
          setFormLoading(false);
        }
      } catch (error) {
        console.error('Polling error:', error);
        clearInterval(interval);
        showError('无法轮询任务状态');
        setFormLoading(false);
      }
    }, 2000);
  }

  function updateProgress(progress) {
    progressFill.style.width = `${progress}%`;
    progressText.textContent = `${Math.round(progress)}%`;
  }

  function validateForm() {
    const requiredFields = form.querySelectorAll('[required]');
    let isValid = true;
    
    // Reset all error states
    form.querySelectorAll('.error-field').forEach(field => {
      field.classList.remove('error-field');
      field.style.borderColor = '';
    });
    
    requiredFields.forEach(field => {
      const hasValue = field.type === 'file' ? field.files.length > 0 : field.value.trim() !== '';
      
      if (!hasValue) {
        isValid = false;
        field.classList.add('error-field');
        field.style.borderColor = '#ef4444';
        
        // Add error animation
        field.style.animation = 'shake 0.5s ease-in-out';
        setTimeout(() => {
          field.style.animation = '';
        }, 500);
      }
    });
    
    // Validate file types
    const srtInput = document.querySelector('input[name="input_file"]');
    const voiceInput = document.querySelector('input[name="voice_files"]');
    
    if (srtInput.files.length > 0) {
      const file = srtInput.files[0];
      const allowedTypes = ['.srt', '.txt'];
      const fileExtension = '.' + file.name.split('.').pop().toLowerCase();
      
      if (!allowedTypes.includes(fileExtension)) {
        isValid = false;
        showError(`不支持的文件格式: ${fileExtension}。请选择 .srt 或 .txt 文件。`);
        return false;
      }
    }
    
    if (voiceInput.files.length > 0) {
      for (let file of voiceInput.files) {
        const allowedTypes = ['.wav', '.mp3'];
        const fileExtension = '.' + file.name.split('.').pop().toLowerCase();
        
        if (!allowedTypes.includes(fileExtension)) {
          isValid = false;
          showError(`不支持的音频格式: ${fileExtension}。请选择 .wav 或 .mp3 文件。`);
          return false;
        }
      }
    }
    
    if (!isValid) {
      showError('请填写所有必填字段');
    }
    
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

  function showStatus(title, message) {
    statusTitle.textContent = title;
    statusMessage.textContent = message;
    progressContainer.style.display = 'none';
    resultSection.style.display = 'none';
  }

  function showProgress() {
    showStatus('处理中...', '正在上传文件并开始配音处理...');
    progressContainer.style.display = 'block';
  }

  function showResult(resultUrl) {
    statusTitle.style.display = 'none';
    statusMessage.style.display = 'none';
    document.querySelector('.status-icon').style.display = 'none';

    downloadLink.href = resultUrl;
    downloadLink.download = resultUrl.split('/').pop();
    resultSection.style.display = 'block';
    progressContainer.style.display = 'none';
    
    // Add success animation
    resultSection.classList.add('success-animation');
    setTimeout(() => {
      resultSection.classList.remove('success-animation');
    }, 600);
  }

  function showSuccess(message) {
    showStatus('完成', message);
    progressContainer.style.display = 'none';
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

  function simulateProgress() {
    let progress = 0;
    const interval = setInterval(() => {
      progress += Math.random() * 15;
      if (progress >= 100) {
        progress = 100;
        clearInterval(interval);
      }
      
      progressFill.style.width = `${progress}%`;
      progressText.textContent = `${Math.round(progress)}%`;
    }, 200);
  }

  // Add some interactive effects
  document.addEventListener('DOMContentLoaded', () => {
    // Add hover effects to form elements
    const formElements = document.querySelectorAll('.form-textarea, .form-select');
    formElements.forEach(element => {
      element.addEventListener('focus', () => {
        element.parentElement.style.transform = 'scale(1.02)';
      });
      
      element.addEventListener('blur', () => {
        element.parentElement.style.transform = 'scale(1)';
      });
    });
  });
});

// Add shake animation for error fields
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
