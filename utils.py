import requests
import os
import re
import uuid

from django.template.defaultfilters import linebreaksbr
from django.conf import settings

from core import models as core_models, files
from journal import models as journal_models
from utils import setting_handler
from submission import models as submission_models


def import_editorial_team(request, reader):
    row_list = [row for row in reader]
    row_list.remove(row_list[0])

    for row in row_list:
        group, c = core_models.EditorialGroup.objects.get_or_create(
            name=row[7],
            journal=request.journal,
            defaults={'sequence': request.journal.next_group_order()})
        country = core_models.Country.objects.get(code=row[6])
        user, c = core_models.Account.objects.get_or_create(
            username=row[3],
            email=row[3],
            defaults={
                'first_name': row[0],
                'middle_name': row[1],
                'last_name': row[2],
                'department': row[4],
                'institution': row[5],
                'country': country,
            }
        )

        core_models.EditorialGroupMember.objects.get_or_create(
            group=group,
            user=user,
            sequence=group.next_member_sequence()
        )


def import_contacts_team(request, reader):
    row_list = [row for row in reader]
    row_list.remove(row_list[0])

    for row in row_list:
        core_models.Contacts.objects.get_or_create(
            content_type=request.model_content_type,
            object_id = request.journal.id,
            name=row[0],
            email=row[1],
            role=row[2],
            sequence=request.journal.next_contact_order()
        )


def import_submission_settings(request, reader):
    row_list = [row for row in reader]
    row_list.remove(row_list[0])

    for row in row_list:
        journal = journal_models.Journal.objects.get(code=row[0])
        setting_handler.save_setting('general', 'copyright_notice', journal, linebreaksbr(row[1]))
        setting_handler.save_setting('general', 'submission_checklist', journal, linebreaksbr(row[2]))
        setting_handler.save_setting('general', 'publication_fees', journal, linebreaksbr(row[3]))
        setting_handler.save_setting('general', 'reviewer_guidelines', journal, linebreaksbr(row[4]))


def generate_review_forms(request):
    from review import models as review_models

    journal_pks = request.POST.getlist('journals')
    journals = [journal_models.Journal.objects.get(pk=pk) for pk in journal_pks]

    for journal in journals:

        default_review_form = review_models.ReviewForm.objects.create(
            journal=journal,
            name='Default Form',
            slug='default-form',
            intro='Please complete the form below.',
            thanks='Thank you for completing the review.'
        )

        main_element = review_models.ReviewFormElement.objects.create(
            name='Review',
            kind='textarea',
            required=True,
            order=1,
            width='large-12 columns',
            help_text='Please add as much detail as you can.'
        )

        default_review_form.elements.add(main_element)


def load_favicons(request):
    journal_pks = request.POST.getlist('journals')
    journals = [journal_models.Journal.objects.get(pk=pk) for pk in journal_pks]

    for journal in journals:
        journal.favicon = request.FILES.get('favicon')
        journal.save()


def load_article_images(request, reader):
    row_list = [row for row in reader]
    row_list.remove(row_list[0])

    for row in row_list:
        article = submission_models.Article.get_article(request.journal, row[0], row[1])

        image = requests.get(row[2], stream=True)
        if image.status_code == 200:

            content_disposition = image.headers['content-disposition']
            filename = re.findall("filename=\"(.+)\"", content_disposition)[0]

            name, extension = os.path.splitext(filename)
            uuid_filename = '{0}{1}'.format(uuid.uuid4(), extension)

            filepath = os.path.join(settings.BASE_DIR, 'files', 'articles', str(article.pk), uuid_filename)

            with open(filepath, 'wb') as f:
                for chunk in image:
                    f.write(chunk)

            new_file = core_models.File.objects.create(
                article_id=article.pk,
                mime_type=files.file_path_mime(filepath),
                original_filename=filename,
                uuid_filename=uuid_filename,
                label='Large Image File',
                privacy='public',
            )
            article.large_image_file = new_file
            article.save()
