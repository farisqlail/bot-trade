import clsx from 'clsx'

export default function MetricCard({ title, value, subtitle, trend, className }) {
  const isPositive = trend > 0
  const isNegative = trend < 0

  return (
    <div className={clsx('bg-gray-900 rounded-xl p-5 border border-gray-800', className)}>
      <p className="text-xs text-gray-500 uppercase tracking-wider">{title}</p>
      <p className="text-2xl font-bold mt-2 text-white">{value}</p>
      {subtitle && (
        <p
          className={clsx('text-sm mt-1', {
            'text-green-400': isPositive,
            'text-red-400': isNegative,
            'text-gray-400': trend === 0 || trend === undefined,
          })}
        >
          {isPositive && '+'}
          {subtitle}
        </p>
      )}
    </div>
  )
}
