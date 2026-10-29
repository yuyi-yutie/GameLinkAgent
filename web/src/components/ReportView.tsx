import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";

interface Props {
  source: string;
  title: string;
}

export function ReportView({ source, title }: Props) {
  return (
    <section className="report">
      <h3>{title}</h3>
      <ReactMarkdown remarkPlugins={[remarkGfm]}>{source}</ReactMarkdown>
    </section>
  );
}
