import { LibraryArticle } from '@/components/library/LibraryArticle'

export default function ArticlePage({ params }: { params: { slug: string } }) {
  return <LibraryArticle key={params.slug} slug={params.slug} />
}
