// Ported from OpenChatCut (AGPL-3.0-or-later, github.com/0xsline/OpenChatCut) src/components/timeline/MenuDrillHeader.tsx @ 9242a95. See src/occ/NOTICE.md.
import { t } from '../../i18n/locale';

export function MenuDrillHeader({ title, onBack }: { title: string; onBack: () => void }) {
  return (
    <button type="button" className="cc-menu-drill-header" aria-label={t('返回{title}', { title })} onClick={onBack}>
      <span aria-hidden>‹</span>
      <span>{title}</span>
    </button>
  );
}
