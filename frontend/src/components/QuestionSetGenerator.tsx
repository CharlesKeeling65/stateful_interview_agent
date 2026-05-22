import { useState, useEffect, useCallback } from 'react'
import {
  createQuestionSet,
  getQuestionSet,
  listQuestionSets,
  reviseQuestion,
  validateQuestionSet,
  getQuestionSetCoverage,
  deleteQuestionSet,
  type QuestionSetResponse,
  type GeneratedQuestionResponse,
  type QuestionRevisionResponse,
  type ValidationReport,
  type CoverageReport,
} from '../api/client'

interface QuestionSetGeneratorProps {
  locale: 'en' | 'zh'
}

export function QuestionSetGenerator({ locale }: QuestionSetGeneratorProps) {
  const [repositoryUrl, setRepositoryUrl] = useState('')
  const [totalQuestions, setTotalQuestions] = useState(40)
  const [codeDetailRatio, setCodeDetailRatio] = useState(0.85)
  const [minCoreFileCoverage, setMinCoreFileCoverage] = useState(0.90)
  
  const [questionSets, setQuestionSets] = useState<QuestionSetResponse[]>([])
  const [selectedQuestionSet, setSelectedQuestionSet] = useState<QuestionSetResponse | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  
  // Revision state
  const [selectedQuestion, setSelectedQuestion] = useState<GeneratedQuestionResponse | null>(null)
  const [chineseInstruction, setChineseInstruction] = useState('')
  const [revisionResult, setRevisionResult] = useState<QuestionRevisionResponse | null>(null)
  const [revising, setRevising] = useState(false)
  
  // Validation and coverage state
  const [validationReport, setValidationReport] = useState<ValidationReport | null>(null)
  const [coverageReport, setCoverageReport] = useState<CoverageReport | null>(null)
  
  // Polling state
  const [, setPolling] = useState(false)
  
  const t = useCallback((key: string) => {
    const translations: Record<string, Record<string, string>> = {
      en: {
        'questionSet.title': 'Question Set Generator',
        'questionSet.description': 'Generate a complete question set for repository code understanding',
        'questionSet.repositoryUrl': 'Repository URL',
        'questionSet.repositoryUrl.placeholder': 'https://github.com/username/repository',
        'questionSet.totalQuestions': 'Total Questions',
        'questionSet.codeDetailRatio': 'Code Detail Ratio',
        'questionSet.minCoreFileCoverage': 'Min Core File Coverage',
        'questionSet.generate': 'Generate Question Set',
        'questionSet.generating': 'Generating...',
        'questionSet.list': 'Question Sets',
        'questionSet.select': 'Select',
        'questionSet.delete': 'Delete',
        'questionSet.questions': 'Questions',
        'questionSet.phase': 'Phase',
        'questionSet.question': 'Question',
        'questionSet.targetFiles': 'Target Files',
        'questionSet.qualityScore': 'Quality Score',
        'questionSet.revise': 'Revise',
        'questionSet.revision.title': 'Revise Question',
        'questionSet.revision.instruction': 'Chinese Instruction',
        'questionSet.revision.instruction.placeholder': '例如：这个问题太泛了，改成具体问 main.py 里的 run_agent 方法',
        'questionSet.revision.submit': 'Revise',
        'questionSet.revision.result': 'Revision Result',
        'questionSet.revision.original': 'Original',
        'questionSet.revision.revised': 'Revised',
        'questionSet.revision.warnings': 'Warnings',
        'questionSet.validation': 'Validation Report',
        'questionSet.validation.isValid': 'Is Valid',
        'questionSet.validation.totalQuestions': 'Total Questions',
        'questionSet.validation.codeDetailCount': 'Code Detail Count',
        'questionSet.validation.codeDetailRatio': 'Code Detail Ratio',
        'questionSet.validation.coreFilesDetected': 'Core Files Detected',
        'questionSet.validation.coreFilesCovered': 'Core Files Covered',
        'questionSet.validation.coreFileCoverage': 'Core File Coverage',
        'questionSet.validation.warnings': 'Warnings',
        'questionSet.validation.errors': 'Errors',
        'questionSet.coverage': 'Coverage Report',
        'questionSet.coverage.totalCoreFiles': 'Total Core Files',
        'questionSet.coverage.coveredCoreFiles': 'Covered Core Files',
        'questionSet.coverage.coveragePercentage': 'Coverage Percentage',
        'questionSet.coverage.uncoveredFiles': 'Uncovered Files',
        'questionSet.status.pending': 'Pending',
        'questionSet.status.analyzing': 'Analyzing',
        'questionSet.status.generating': 'Generating',
        'questionSet.status.validating': 'Validating',
        'questionSet.status.completed': 'Completed',
        'questionSet.status.failed': 'Failed',
        'questionSet.error': 'Error',
        'questionSet.noQuestionSets': 'No question sets yet',
        'questionSet.selectQuestionSet': 'Select a question set to view details',
      },
      zh: {
        'questionSet.title': '问题集生成器',
        'questionSet.description': '为代码仓库生成完整的问题集，用于代码理解',
        'questionSet.repositoryUrl': '仓库 URL',
        'questionSet.repositoryUrl.placeholder': 'https://github.com/用户名/仓库名',
        'questionSet.totalQuestions': '问题总数',
        'questionSet.codeDetailRatio': '代码细节比例',
        'questionSet.minCoreFileCoverage': '最小核心文件覆盖率',
        'questionSet.generate': '生成问题集',
        'questionSet.generating': '生成中...',
        'questionSet.list': '问题集列表',
        'questionSet.select': '选择',
        'questionSet.delete': '删除',
        'questionSet.questions': '问题',
        'questionSet.phase': '阶段',
        'questionSet.question': '问题',
        'questionSet.targetFiles': '目标文件',
        'questionSet.qualityScore': '质量分数',
        'questionSet.revise': '修订',
        'questionSet.revision.title': '修订问题',
        'questionSet.revision.instruction': '中文指令',
        'questionSet.revision.instruction.placeholder': '例如：这个问题太泛了，改成具体问 main.py 里的 run_agent 方法',
        'questionSet.revision.submit': '修订',
        'questionSet.revision.result': '修订结果',
        'questionSet.revision.original': '原始问题',
        'questionSet.revision.revised': '修订后',
        'questionSet.revision.warnings': '警告',
        'questionSet.validation': '验证报告',
        'questionSet.validation.isValid': '是否有效',
        'questionSet.validation.totalQuestions': '问题总数',
        'questionSet.validation.codeDetailCount': '代码细节问题数',
        'questionSet.validation.codeDetailRatio': '代码细节比例',
        'questionSet.validation.coreFilesDetected': '检测到的核心文件',
        'questionSet.validation.coreFilesCovered': '已覆盖的核心文件',
        'questionSet.validation.coreFileCoverage': '核心文件覆盖率',
        'questionSet.validation.warnings': '警告',
        'questionSet.validation.errors': '错误',
        'questionSet.coverage': '覆盖率报告',
        'questionSet.coverage.totalCoreFiles': '核心文件总数',
        'questionSet.coverage.coveredCoreFiles': '已覆盖的核心文件',
        'questionSet.coverage.coveragePercentage': '覆盖率百分比',
        'questionSet.coverage.uncoveredFiles': '未覆盖的文件',
        'questionSet.status.pending': '待处理',
        'questionSet.status.analyzing': '分析中',
        'questionSet.status.generating': '生成中',
        'questionSet.status.validating': '验证中',
        'questionSet.status.completed': '已完成',
        'questionSet.status.failed': '失败',
        'questionSet.error': '错误',
        'questionSet.noQuestionSets': '暂无问题集',
        'questionSet.selectQuestionSet': '选择一个问题集查看详情',
      },
    }
    return translations[locale]?.[key] || key
  }, [locale])
  
  // Load question sets on mount
  useEffect(() => {
    loadQuestionSets()
  }, [])
  
  // Poll for status updates
  useEffect(() => {
    if (!selectedQuestionSet || selectedQuestionSet.status === 'completed' || selectedQuestionSet.status === 'failed') {
      setPolling(false)
      return
    }
    
    setPolling(true)
    const interval = setInterval(async () => {
      try {
        const updated = await getQuestionSet(selectedQuestionSet.id)
        setSelectedQuestionSet(updated)
        
        if (updated.status === 'completed' || updated.status === 'failed') {
          setPolling(false)
          clearInterval(interval)
          
          // Reload validation and coverage
          if (updated.status === 'completed') {
            const [validation, coverage] = await Promise.all([
              validateQuestionSet(updated.id),
              getQuestionSetCoverage(updated.id),
            ])
            setValidationReport(validation)
            setCoverageReport(coverage)
          }
        }
      } catch (err) {
        console.error('Polling error:', err)
      }
    }, 2000)
    
    return () => {
      clearInterval(interval)
      setPolling(false)
    }
  }, [selectedQuestionSet])
  
  const loadQuestionSets = async () => {
    try {
      const response = await listQuestionSets()
      setQuestionSets(response.question_sets)
    } catch (err) {
      console.error('Failed to load question sets:', err)
    }
  }
  
  const handleGenerate = async () => {
    if (!repositoryUrl) {
      setError('Please enter a repository URL')
      return
    }
    
    setLoading(true)
    setError(null)
    
    try {
      const questionSet = await createQuestionSet({
        repository_url: repositoryUrl,
        total_questions: totalQuestions,
        code_detail_ratio: codeDetailRatio,
        min_core_file_coverage: minCoreFileCoverage,
      })
      
      setSelectedQuestionSet(questionSet)
      setQuestionSets(prev => [questionSet, ...prev])
      
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to generate question set')
    } finally {
      setLoading(false)
    }
  }
  
  const handleSelectQuestionSet = async (questionSet: QuestionSetResponse) => {
    setSelectedQuestionSet(questionSet)
    setSelectedQuestion(null)
    setRevisionResult(null)
    setChineseInstruction('')
    
    // Load validation and coverage if completed
    if (questionSet.status === 'completed') {
      try {
        const [validation, coverage] = await Promise.all([
          validateQuestionSet(questionSet.id),
          getQuestionSetCoverage(questionSet.id),
        ])
        setValidationReport(validation)
        setCoverageReport(coverage)
      } catch (err) {
        console.error('Failed to load reports:', err)
      }
    }
  }
  
  const handleDeleteQuestionSet = async (questionSetId: number) => {
    if (!confirm('Are you sure you want to delete this question set?')) {
      return
    }
    
    try {
      await deleteQuestionSet(questionSetId)
      setQuestionSets(prev => prev.filter(qs => qs.id !== questionSetId))
      
      if (selectedQuestionSet?.id === questionSetId) {
        setSelectedQuestionSet(null)
        setValidationReport(null)
        setCoverageReport(null)
      }
    } catch (err) {
      console.error('Failed to delete question set:', err)
    }
  }
  
  const handleReviseQuestion = async () => {
    if (!selectedQuestionSet || !selectedQuestion || !chineseInstruction) {
      return
    }
    
    setRevising(true)
    
    try {
      const result = await reviseQuestion(selectedQuestionSet.id, {
        question_id: selectedQuestion.id,
        chinese_instruction: chineseInstruction,
      })
      
      setRevisionResult(result)
      
      // Update question in the list
      if (selectedQuestionSet) {
        const updatedQuestions = selectedQuestionSet.questions.map(q => 
          q.id === selectedQuestion.id 
            ? { ...q, question_text: result.revised_question }
            : q
        )
        setSelectedQuestionSet({
          ...selectedQuestionSet,
          questions: updatedQuestions,
        })
      }
      
    } catch (err) {
      console.error('Failed to revise question:', err)
    } finally {
      setRevising(false)
    }
  }
  
  const getStatusColor = (status: string) => {
    switch (status) {
      case 'completed': return 'text-green-600'
      case 'failed': return 'text-red-600'
      case 'analyzing':
      case 'generating':
      case 'validating': return 'text-yellow-600'
      default: return 'text-gray-600'
    }
  }
  
  const getPhaseColor = (phase: string) => {
    switch (phase) {
      case 'Panorama Mapping': return 'bg-blue-100 text-blue-800'
      case 'Architecture Understanding': return 'bg-purple-100 text-purple-800'
      case 'Code Detail Completion': return 'bg-green-100 text-green-800'
      case 'Use Cases & Scenarios': return 'bg-orange-100 text-orange-800'
      default: return 'bg-gray-100 text-gray-800'
    }
  }
  
  return (
    <div className="container mx-auto p-4">
      <h1 className="text-2xl font-bold mb-4">{t('questionSet.title')}</h1>
      <p className="text-gray-600 mb-6">{t('questionSet.description')}</p>
      
      {/* Generation Form */}
      <div className="bg-white rounded-lg shadow p-6 mb-6">
        <h2 className="text-lg font-semibold mb-4">{t('questionSet.generate')}</h2>
        
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4 mb-4">
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">
              {t('questionSet.repositoryUrl')}
            </label>
            <input
              type="text"
              value={repositoryUrl}
              onChange={(e) => setRepositoryUrl(e.target.value)}
              placeholder={t('questionSet.repositoryUrl.placeholder')}
              className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
            />
          </div>
          
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">
              {t('questionSet.totalQuestions')}
            </label>
            <input
              type="number"
              value={totalQuestions}
              onChange={(e) => setTotalQuestions(parseInt(e.target.value) || 40)}
              min={35}
              max={100}
              className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
            />
          </div>
          
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">
              {t('questionSet.codeDetailRatio')}
            </label>
            <input
              type="number"
              value={codeDetailRatio}
              onChange={(e) => setCodeDetailRatio(parseFloat(e.target.value) || 0.85)}
              min={0.5}
              max={1.0}
              step={0.01}
              className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
            />
          </div>
          
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">
              {t('questionSet.minCoreFileCoverage')}
            </label>
            <input
              type="number"
              value={minCoreFileCoverage}
              onChange={(e) => setMinCoreFileCoverage(parseFloat(e.target.value) || 0.90)}
              min={0.5}
              max={1.0}
              step={0.01}
              className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
            />
          </div>
        </div>
        
        {error && (
          <div className="bg-red-50 border border-red-200 text-red-700 px-4 py-3 rounded mb-4">
            {error}
          </div>
        )}
        
        <button
          onClick={handleGenerate}
          disabled={loading}
          className="bg-blue-500 text-white px-4 py-2 rounded hover:bg-blue-600 disabled:opacity-50"
        >
          {loading ? t('questionSet.generating') : t('questionSet.generate')}
        </button>
      </div>
      
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Question Sets List */}
        <div className="bg-white rounded-lg shadow p-6">
          <h2 className="text-lg font-semibold mb-4">{t('questionSet.list')}</h2>
          
          {questionSets.length === 0 ? (
            <p className="text-gray-500">{t('questionSet.noQuestionSets')}</p>
          ) : (
            <div className="space-y-3">
              {questionSets.map(qs => (
                <div
                  key={qs.id}
                  className={`p-3 border rounded cursor-pointer ${
                    selectedQuestionSet?.id === qs.id 
                      ? 'border-blue-500 bg-blue-50' 
                      : 'border-gray-200 hover:border-gray-300'
                  }`}
                  onClick={() => handleSelectQuestionSet(qs)}
                >
                  <div className="flex justify-between items-start">
                    <div>
                      <div className="font-medium text-sm truncate max-w-[200px]">
                        {qs.repository_url}
                      </div>
                      <div className={`text-xs ${getStatusColor(qs.status)}`}>
                        {t(`questionSet.status.${qs.status}`)}
                      </div>
                    </div>
                    <button
                      onClick={(e) => {
                        e.stopPropagation()
                        handleDeleteQuestionSet(qs.id)
                      }}
                      className="text-red-500 hover:text-red-700 text-xs"
                    >
                      {t('questionSet.delete')}
                    </button>
                  </div>
                  <div className="text-xs text-gray-500 mt-1">
                    {qs.question_count} {t('questionSet.questions')}
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
        
        {/* Questions List */}
        <div className="bg-white rounded-lg shadow p-6">
          <h2 className="text-lg font-semibold mb-4">
            {selectedQuestionSet 
              ? `${t('questionSet.questions')} (${selectedQuestionSet.question_count})`
              : t('questionSet.selectQuestionSet')
            }
          </h2>
          
          {selectedQuestionSet && (
            <div className="space-y-3 max-h-[600px] overflow-y-auto">
              {selectedQuestionSet.questions.map(q => (
                <div
                  key={q.id}
                  className={`p-3 border rounded cursor-pointer ${
                    selectedQuestion?.id === q.id 
                      ? 'border-green-500 bg-green-50' 
                      : 'border-gray-200 hover:border-gray-300'
                  }`}
                  onClick={() => setSelectedQuestion(q)}
                >
                  <div className="flex justify-between items-start mb-1">
                    <span className={`text-xs px-2 py-1 rounded ${getPhaseColor(q.phase)}`}>
                      {q.phase}
                    </span>
                    <span className="text-xs text-gray-500">
                      Q{q.question_no}
                    </span>
                  </div>
                  <div className="text-sm text-gray-800 line-clamp-2">
                    {q.question_text}
                  </div>
                  {q.target_files.length > 0 && (
                    <div className="text-xs text-gray-500 mt-1">
                      {t('questionSet.targetFiles')}: {q.target_files.slice(0, 2).join(', ')}
                      {q.target_files.length > 2 && ` +${q.target_files.length - 2}`}
                    </div>
                  )}
                </div>
              ))}
            </div>
          )}
        </div>
        
        {/* Question Details and Revision */}
        <div className="bg-white rounded-lg shadow p-6">
          {selectedQuestion ? (
            <>
              <h2 className="text-lg font-semibold mb-4">{t('questionSet.revision.title')}</h2>
              
              <div className="mb-4">
                <div className="text-sm text-gray-500 mb-1">{t('questionSet.question')}</div>
                <div className="p-3 bg-gray-50 rounded">
                  {selectedQuestion.question_text}
                </div>
              </div>
              
              <div className="mb-4">
                <label className="block text-sm font-medium text-gray-700 mb-1">
                  {t('questionSet.revision.instruction')}
                </label>
                <textarea
                  value={chineseInstruction}
                  onChange={(e) => setChineseInstruction(e.target.value)}
                  placeholder={t('questionSet.revision.instruction.placeholder')}
                  className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
                  rows={3}
                />
              </div>
              
              <button
                onClick={handleReviseQuestion}
                disabled={revising || !chineseInstruction}
                className="bg-green-500 text-white px-4 py-2 rounded hover:bg-green-600 disabled:opacity-50 mb-4"
              >
                {revising ? '...' : t('questionSet.revision.submit')}
              </button>
              
              {revisionResult && (
                <div className="border-t pt-4">
                  <h3 className="font-medium mb-2">{t('questionSet.revision.result')}</h3>
                  
                  <div className="mb-2">
                    <div className="text-xs text-gray-500">{t('questionSet.revision.original')}</div>
                    <div className="text-sm bg-red-50 p-2 rounded">
                      {revisionResult.original_question}
                    </div>
                  </div>
                  
                  <div className="mb-2">
                    <div className="text-xs text-gray-500">{t('questionSet.revision.revised')}</div>
                    <div className="text-sm bg-green-50 p-2 rounded">
                      {revisionResult.revised_question}
                    </div>
                  </div>
                  
                  {revisionResult.warnings.length > 0 && (
                    <div className="mb-2">
                      <div className="text-xs text-gray-500">{t('questionSet.revision.warnings')}</div>
                      <ul className="text-sm text-yellow-600 list-disc list-inside">
                        {revisionResult.warnings.map((warning, i) => (
                          <li key={i}>{warning}</li>
                        ))}
                      </ul>
                    </div>
                  )}
                </div>
              )}
            </>
          ) : (
            <div className="text-gray-500 text-center py-8">
              {t('questionSet.selectQuestionSet')}
            </div>
          )}
        </div>
      </div>
      
      {/* Validation and Coverage Reports */}
      {selectedQuestionSet?.status === 'completed' && (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-6 mt-6">
          {/* Validation Report */}
          <div className="bg-white rounded-lg shadow p-6">
            <h2 className="text-lg font-semibold mb-4">{t('questionSet.validation')}</h2>
            
            {validationReport && (
              <div className="space-y-3">
                <div className="flex justify-between">
                  <span className="text-sm text-gray-600">{t('questionSet.validation.isValid')}</span>
                  <span className={`font-medium ${validationReport.is_valid ? 'text-green-600' : 'text-red-600'}`}>
                    {validationReport.is_valid ? '✓' : '✗'}
                  </span>
                </div>
                
                <div className="flex justify-between">
                  <span className="text-sm text-gray-600">{t('questionSet.validation.totalQuestions')}</span>
                  <span className="font-medium">{validationReport.total_questions}</span>
                </div>
                
                <div className="flex justify-between">
                  <span className="text-sm text-gray-600">{t('questionSet.validation.codeDetailCount')}</span>
                  <span className="font-medium">{validationReport.code_detail_count}</span>
                </div>
                
                <div className="flex justify-between">
                  <span className="text-sm text-gray-600">{t('questionSet.validation.codeDetailRatio')}</span>
                  <span className="font-medium">
                    {(validationReport.code_detail_ratio * 100).toFixed(1)}%
                  </span>
                </div>
                
                <div className="flex justify-between">
                  <span className="text-sm text-gray-600">{t('questionSet.validation.coreFilesDetected')}</span>
                  <span className="font-medium">{validationReport.core_files_detected}</span>
                </div>
                
                <div className="flex justify-between">
                  <span className="text-sm text-gray-600">{t('questionSet.validation.coreFilesCovered')}</span>
                  <span className="font-medium">{validationReport.core_files_covered}</span>
                </div>
                
                <div className="flex justify-between">
                  <span className="text-sm text-gray-600">{t('questionSet.validation.coreFileCoverage')}</span>
                  <span className="font-medium">
                    {(validationReport.core_file_coverage * 100).toFixed(1)}%
                  </span>
                </div>
                
                {validationReport.warnings.length > 0 && (
                  <div>
                    <div className="text-sm text-gray-600 mb-1">{t('questionSet.validation.warnings')}</div>
                    <ul className="text-sm text-yellow-600 list-disc list-inside">
                      {validationReport.warnings.map((warning, i) => (
                        <li key={i}>{warning}</li>
                      ))}
                    </ul>
                  </div>
                )}
                
                {validationReport.errors.length > 0 && (
                  <div>
                    <div className="text-sm text-gray-600 mb-1">{t('questionSet.validation.errors')}</div>
                    <ul className="text-sm text-red-600 list-disc list-inside">
                      {validationReport.errors.map((error, i) => (
                        <li key={i}>{error}</li>
                      ))}
                    </ul>
                  </div>
                )}
              </div>
            )}
          </div>
          
          {/* Coverage Report */}
          <div className="bg-white rounded-lg shadow p-6">
            <h2 className="text-lg font-semibold mb-4">{t('questionSet.coverage')}</h2>
            
            {coverageReport && (
              <div className="space-y-3">
                <div className="flex justify-between">
                  <span className="text-sm text-gray-600">{t('questionSet.coverage.totalCoreFiles')}</span>
                  <span className="font-medium">{coverageReport.total_core_files}</span>
                </div>
                
                <div className="flex justify-between">
                  <span className="text-sm text-gray-600">{t('questionSet.coverage.coveredCoreFiles')}</span>
                  <span className="font-medium">{coverageReport.covered_core_files}</span>
                </div>
                
                <div className="flex justify-between">
                  <span className="text-sm text-gray-600">{t('questionSet.coverage.coveragePercentage')}</span>
                  <span className="font-medium">
                    {(coverageReport.coverage_percentage * 100).toFixed(1)}%
                  </span>
                </div>
                
                {coverageReport.uncovered_files.length > 0 && (
                  <div>
                    <div className="text-sm text-gray-600 mb-1">{t('questionSet.coverage.uncoveredFiles')}</div>
                    <ul className="text-sm text-gray-500 list-disc list-inside max-h-40 overflow-y-auto">
                      {coverageReport.uncovered_files.map((file, i) => (
                        <li key={i}>{file}</li>
                      ))}
                    </ul>
                  </div>
                )}
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  )
}
