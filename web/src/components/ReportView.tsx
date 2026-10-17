import ReactMarkdown from "react-markdown";

interface Props {
  source: string;
  title: string;
}

export function ReportView({ source, title }: Props) {
  return (
    <section className="report">
      <h3>{title}</h3>
      <ReactMarkdown>{source}</ReactMarkdown>
    </section>
  );
}
