import {
  MessageSquare,
  FileText,
  Share2,
  Clock,
  BarChart3,
  History,
  Settings,
} from 'lucide-react';

const icons = {
  message: MessageSquare,
  file: FileText,
  graph: Share2,
  clock: Clock,
  chart: BarChart3,
  history: History,
  settings: Settings,
};

interface PlaceholderPageProps {
  title: string;
  description: string;
  icon: keyof typeof icons;
}

export default function PlaceholderPage({ title, description, icon }: PlaceholderPageProps) {
  const Icon = icons[icon];

  return (
    <div className="page">
      <div className="placeholder-page">
        <div className="placeholder-icon">
          <Icon size={36} />
        </div>
        <h1 className="placeholder-title">{title}</h1>
        <p className="placeholder-text">{description}</p>
      </div>
    </div>
  );
}
