from django.contrib import admin
from .models import Document, DocumentConsent, DocumentAccessLog


@admin.register(Document)
class DocumentAdmin(admin.ModelAdmin):
    list_display = ('id', 'title', 'owner', 'uploaded_by', 'document_type', 'is_deleted', 'created_at')
    list_filter = ('document_type', 'is_deleted', 'created_at')
    search_fields = ('title', 'owner__contact', 'uploaded_by__contact')
    readonly_fields = ('id', 'created_at', 'updated_at')
    raw_id_fields = ('owner', 'uploaded_by', 'appointment')


@admin.register(DocumentConsent)
class DocumentConsentAdmin(admin.ModelAdmin):
    list_display = ('id', 'document', 'doctor', 'status', 'created_at', 'expires_at')
    list_filter = ('status', 'created_at')
    search_fields = ('document__title', 'doctor__user__contact')
    readonly_fields = ('id', 'created_at', 'actioned_at')
    raw_id_fields = ('document', 'doctor')


@admin.register(DocumentAccessLog)
class DocumentAccessLogAdmin(admin.ModelAdmin):
    list_display = ('id', 'document', 'accessed_by', 'accessed_at', 'ip_address')
    list_filter = ('accessed_at',)
    search_fields = ('document__title', 'accessed_by__contact')
    readonly_fields = ('id', 'document', 'accessed_by', 'accessed_at', 'ip_address')

    def has_add_permission(self, request):
        return False  # immutable audit log

    def has_change_permission(self, request, obj=None):
        return False  # no edits
