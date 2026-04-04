import type { Translator } from '../i18n'
import { ActionButton } from './ActionButton'
import { ChevronLeftIcon, ChevronRightIcon } from './Icons'

type TranscriptPaginationProps = {
  currentPage: number
  onPageChange: (page: number) => void
  onPageSizeChange: (pageSize: number) => void
  pageSize: number
  pageSizes?: number[]
  t: Translator
  totalItems: number
  totalPages: number
}

export function TranscriptPagination({
  currentPage,
  onPageChange,
  onPageSizeChange,
  pageSize,
  pageSizes = [5, 10],
  t,
  totalItems,
  totalPages,
}: TranscriptPaginationProps) {
  if (totalItems === 0) {
    return null
  }

  if (totalItems <= Math.min(...pageSizes)) {
    return null
  }

  const start = (currentPage - 1) * pageSize + 1
  const end = Math.min(currentPage * pageSize, totalItems)

  return (
    <div className="flex flex-wrap items-center justify-between gap-3 rounded-[1.5rem] border border-slate-200 bg-slate-50/80 px-4 py-3">
      <div>
        <p className="text-xs font-medium text-slate-600">
          {t('transcript.showingTurns')} {start}-{end} {t('transcript.of')} {totalItems}
        </p>
      </div>

      <div className="flex flex-wrap items-center gap-2">
        <div className="inline-flex rounded-full border border-slate-200 bg-white p-1">
          {pageSizes.map((size) => {
            const active = size === pageSize
            return (
              <button
                key={size}
                type="button"
                className={`rounded-full px-3 py-1.5 text-xs font-medium transition ${
                  active
                    ? 'bg-slate-950 text-white'
                    : 'text-slate-600 hover:bg-slate-100'
                }`}
                onClick={() => onPageSizeChange(size)}
                aria-pressed={active}
              >
                {size}/{t('transcript.perPage')}
              </button>
            )
          })}
        </div>

        <ActionButton
          aria-label={`${t('transcript.page')} ${currentPage - 1}`}
          disabled={currentPage <= 1}
          icon={<ChevronLeftIcon />}
          onClick={() => onPageChange(currentPage - 1)}
          title={`${t('transcript.page')} ${currentPage - 1}`}
          type="button"
          variant="secondary"
        />
        <span className="min-w-20 text-center text-xs font-semibold uppercase tracking-[0.16em] text-slate-500">
          {t('transcript.page')} {currentPage}/{totalPages}
        </span>
        <ActionButton
          aria-label={`${t('transcript.page')} ${currentPage + 1}`}
          disabled={currentPage >= totalPages}
          icon={<ChevronRightIcon />}
          onClick={() => onPageChange(currentPage + 1)}
          title={`${t('transcript.page')} ${currentPage + 1}`}
          type="button"
          variant="secondary"
        />
      </div>
    </div>
  )
}
