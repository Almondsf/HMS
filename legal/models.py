'''
The terms of service and privacy policy shown on the platform site. Lives
in the shared (public) schema.

Each change is a new version: a published version is never edited, so what
someone accepted at signup (recorded on the signup) can always be shown.
'''

from django.db import models

from helpers.models import TrackingModel

FORMAT_HELP = (
    'Simple formatting: "# " starts a heading, "## " a subheading, "- " a list item; '
    'leave a blank line between paragraphs.'
)


class LegalDocument(TrackingModel):
    class Kind(models.TextChoices):
        TERMS = 'terms', 'Terms of service'
        PRIVACY = 'privacy', 'Privacy policy'

    kind = models.CharField(max_length=20, choices=Kind.choices)
    version = models.CharField(max_length=20, help_text='e.g. the date: 2026-11-01')
    body = models.TextField(help_text=FORMAT_HELP)
    is_draft = models.BooleanField(
        default=True, help_text='Shows a "draft, under legal review" notice. Untick once a lawyer has approved it.'
    )
    published_at = models.DateTimeField(null=True, blank=True, help_text='Set by the "Publish" action; then locked')

    class Meta:
        ordering = ['kind', '-published_at']
        constraints = [models.UniqueConstraint(fields=['kind', 'version'], name='one_legal_version')]

    def __str__(self):
        return f'{self.get_kind_display()} {self.version}{" (draft)" if self.is_draft else ""}'

    @classmethod
    def current(cls, kind):
        return cls.objects.filter(kind=kind, published_at__isnull=False).order_by('-published_at').first()
