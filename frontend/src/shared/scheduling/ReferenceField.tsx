import { forwardRef, type InputHTMLAttributes } from 'react';
import { CalendarDays, ChevronDown, Clock3 } from 'lucide-react';
import './reference-field.css';

type Props = Omit<InputHTMLAttributes<HTMLInputElement>, 'type'> & {
  type: 'date' | 'time';
  text?: string;
  icon?: boolean;
  chevron?: boolean;
  wrapperClassName?: string;
};

/** Native, keyboard-accessible pickers with a consistent visual surface across platforms. */
const ReferenceField = forwardRef<HTMLInputElement, Props>(function ReferenceField({ type, text, icon = true, chevron = true, wrapperClassName = '', value, disabled, onClick, ...props }, ref) {
  const raw = String(value || '');
  const label = text ?? (type === 'date' && /^\d{4}-\d{2}-\d{2}$/.test(raw)
    ? new Intl.DateTimeFormat('en-GB', { timeZone:'UTC', weekday:'short', day:'numeric', month:'short', year:'numeric' }).format(new Date(`${raw}T12:00Z`))
    : raw || (type === 'date' ? 'Select date' : 'Select time'));
  const Icon = type === 'date' ? CalendarDays : Clock3;
  return <span className={`reference-native-field ${wrapperClassName}`} data-disabled={disabled || undefined}>
    {icon && <Icon size={19} aria-hidden="true"/>}<span>{label}</span>{chevron && <ChevronDown size={16} aria-hidden="true"/>}
    <input {...props} ref={ref} type={type} value={value} disabled={disabled} onClick={event=>{
      onClick?.(event);
      if (!event.defaultPrevented && !disabled) {
        try { event.currentTarget.showPicker?.(); } catch { /* Native keyboard editing remains available. */ }
      }
    }}/>
  </span>;
});

export default ReferenceField;
