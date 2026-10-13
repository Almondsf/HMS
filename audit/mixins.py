from .recorder import Category, record
from .registry import patient_id_for, resource_type


class AuditedReadMixin:
    '''
    Records who viewed which records. Add to viewsets serving patient data.
    List views log the ids (and patients) on the returned page only.
    '''

    def get_object(self):
        self._audited_object = super().get_object()
        return self._audited_object

    def retrieve(self, request, *args, **kwargs):
        response = super().retrieve(request, *args, **kwargs)
        record('view', Category.DATA_ACCESS, resource=self._audited_object)
        return response

    def paginate_queryset(self, queryset):
        self._audited_page = super().paginate_queryset(queryset)
        return self._audited_page

    def list(self, request, *args, **kwargs):
        response = super().list(request, *args, **kwargs)
        page = getattr(self, '_audited_page', None) or []
        record(
            'list', Category.DATA_ACCESS,
            resource_type_name=resource_type(self.get_queryset().model),
            metadata={
                'ids': [obj.pk for obj in page],
                'patient_ids': sorted({pid for obj in page if (pid := patient_id_for(obj)) is not None}),
                'query': request.query_params.dict(),
            },
        )
        return response
