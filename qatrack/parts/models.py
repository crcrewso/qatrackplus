from decimal import Decimal

from django.core.validators import MinValueValidator
from django.db import models
from django.urls import reverse
from django.utils.html import format_html
from django.utils.translation import gettext as _
from django.utils.translation import gettext_lazy as _l

from qatrack.service_log import models as sl_models
from qatrack.units import models as u_models


class Supplier(models.Model):

    name = models.CharField(
        verbose_name=_l("supplier"),
        max_length=32,
        unique=True,
        help_text=_l("Enter a unique name for this supplier"),
    )
    address = models.TextField(
        verbose_name=_l("address"),
        blank=True,
    )
    phone_number = models.CharField(
        verbose_name=_l("phone number"),
        blank=True,
        max_length=31,
        help_text=_l("Company phone number"),
    )
    website = models.URLField(
        verbose_name=_l("website"),
        blank=True,
        help_text=_l("Enter a URL for the company"),
    )
    notes = models.TextField(
        verbose_name=_l("notes"),
        max_length=255,
        blank=True,
        null=True,
        help_text=_l('Additional comments about this supplier'),
    )

    class Meta:
        ordering = ('name',)

    def get_absolute_url(self):
        return reverse("supplier_details", kwargs={"pk": self.pk})

    def get_website_tag(self):
        if self.website:
            return format_html(
                '<a href="%s" title="%s">%s</a>' % (
                    self.website,
                    _("Click to visit this suppliers website"),
                    self.website,
                )
            )
        return ""

    def __str__(self):
        return self.name


class Contact(models.Model):

    supplier = models.ForeignKey(
        Supplier,
        verbose_name=_("supplier"),
        on_delete=models.CASCADE,
    )

    first_name = models.CharField(
        max_length=64,
        verbose_name=_("first name"),
        help_text=_l("Enter this persons first name"),
    )
    last_name = models.CharField(
        max_length=64,
        verbose_name=_("last name"),
        help_text=_l("Enter this persons last name"),
    )

    email = models.EmailField(
        verbose_name=_("email"),
        help_text=_l("Enter this persons email address"),
    )

    phone_number = models.CharField(
        verbose_name=_l("phone number"),
        blank=True,
        max_length=31,
        help_text=_l("Contact phone number"),
    )

    class Meta:
        verbose_name = _l('Contact')
        verbose_name_plural = _l('Contacts')
        unique_together = ('first_name', 'last_name', 'supplier')

    def __str__(self):
        return self.last_name + ', ' + self.first_name + ' (' + self.supplier.name + ')'

    def get_full_name(self):
        return str(self)


class RoomManager(models.Manager):

    def get_queryset(self):
        return super(RoomManager, self).get_queryset().select_related('site')


class Room(models.Model):

    site = models.ForeignKey(
        u_models.Site,
        verbose_name=_l("site"),
        on_delete=models.CASCADE,
        blank=True,
        null=True,
        help_text=_l('Site this storage room is located')
    )
    name = models.CharField(
        verbose_name=_l("name"),
        max_length=32,
        help_text=_l('Name of room or room number'),
    )

    objects = RoomManager()

    class Meta:
        ordering = ['site', 'name']
        unique_together = ['site', 'name']

    def __str__(self):
        return '%s%s' % (self.name, ' (%s)' % self.site.name if self.site else '')

    def save(self, *args, **kwargs):
        new = self.pk is None
        super().save(*args, **kwargs)
        if new:
            # Create generic storage (ie, no location)
            Storage.objects.create(room=self)


class StorageManager(models.Manager):

    def get_queryset(self):
        return super(StorageManager, self).get_queryset().select_related('room', 'room__site').order_by('location')

    def get_queryset_for_room(self, room):
        return super().get_queryset().filter(room=room).order_by('location')


class Storage(models.Model):

    room = models.ForeignKey(
        Room,
        verbose_name=_l("room"),
        blank=True,
        null=True,
        help_text=_l('Room for part storage'),
        on_delete=models.CASCADE,
    )

    location = models.CharField(
        verbose_name=_l("location"),
        max_length=32,
        blank=True,
        null=True,
        help_text=_l('Where is this storage located?'),
    )
    description = models.TextField(
        verbose_name=_l("description"),
        max_length=255,
        null=True,
        blank=True,
        help_text=_l("Optional description of this storage"),
    )

    objects = StorageManager()

    class Meta:
        verbose_name_plural = _l("Storage")
        unique_together = ['room', 'location']

    def __str__(self):
        items = []
        if self.room:
            if self.room.site:
                items.append(self.room.site.name)
            items.append(self.room.name)
        if self.location:
            items.append(self.location)
        else:
            items.append('<%s>' % _("no location"))

        return ' - '.join(items)


class PartCategory(models.Model):

    name = models.CharField(
        verbose_name=_l("part category"),
        max_length=64,
        help_text=_l("Enter a name for this part category (e.g. Linac Parts, Table Parts etc)"),
    )

    class Meta:
        verbose_name_plural = _l("Categories")

    def __str__(self):
        return self.name


class Part(models.Model):

    name = models.CharField(
        verbose_name=_l("name"),
        help_text=_l('Brief name describing this part'),
        max_length=255,
    )
    part_category = models.ForeignKey(
        PartCategory,
        verbose_name=_l("part category"),
        on_delete=models.SET_NULL,
        blank=True,
        null=True,
        help_text=_l("Select what category this part is"),
    )
    suppliers = models.ManyToManyField(
        Supplier,
        verbose_name=_l("suppliers"),
        blank=True,
        help_text=_l('Suppliers of this part'),
        related_name='parts',
        through='PartSupplierCollection',
    )
    storage = models.ManyToManyField(
        Storage,
        verbose_name=_l("storage"),
        through='PartStorageCollection',
        related_name='parts',
        help_text=_l('Storage locations for this part'),
    )

    part_number = models.CharField(
        verbose_name=_l("part number"),
        max_length=32,
        help_text=_l("Enter the part number for this part."),
        blank=True,
    )

    new_or_used = models.CharField(
        verbose_name=_l("New or Used"),
        choices=[("both", _l("New & Used")), ("new", _l("New")), ("used", _l("Used"))],
        default="both",
        max_length=12,
        help_text=_l("Is this for tracking inventory of new, used, or both"),
    )

    alt_part_number = models.CharField(
        verbose_name=_l('Alternate part number'),
        max_length=32,
        blank=True,
        null=True,
        help_text=_l('Is this part also identified by a different number?'),
    )
    quantity_min = models.PositiveIntegerField(
        verbose_name=_l("Notification level"),
        default=0,
        help_text=_l('Notify when the quantity of this part in storage falls below this number'),
    )
    quantity_current = models.PositiveIntegerField(
        verbose_name=_l("current quantity"),
        help_text=_l('The number of parts in storage currently'),
        default=0,
        editable=False,
    )
    cost = models.DecimalField(
        verbose_name=_l("cost"),
        default=0,
        decimal_places=2,
        max_digits=10,
        help_text=_l('Cost of this part'),
        null=True,
        blank=True,
        validators=[MinValueValidator(Decimal('0.00'))]
    )
    notes = models.TextField(
        verbose_name=_l("notes"),
        max_length=255,
        blank=True,
        null=True,
        help_text=_l('Additional comments about this part'),
    )
    is_obsolete = models.BooleanField(default=False, help_text=_l('Is this part now obsolete?'))

    class Meta:
        ordering = ['part_number']
        unique_together = [
            ('part_number', 'new_or_used'),
        ]

    def __str__(self):

        pn = self.part_number or "N/A"

        if self.alt_part_number:
            pn += ' (%s)' % self.alt_part_number

        return '%s - %s' % (pn, self.name)

    def set_quantity_current(self):
        qs = PartStorageCollection.objects.filter(part=self, storage__isnull=False)
        initial_quantity = self.quantity_current
        if qs.exists():
            self.quantity_current = qs.aggregate(models.Sum('quantity'))['quantity__sum']
        else:
            self.quantity_current = 0
        self.quantity_current = self.quantity_current if self.quantity_current >= 0 else 0

        quantity_changed = initial_quantity != self.quantity_current
        update_fields = ['quantity_current'] if quantity_changed else None

        self.save(update_fields=update_fields)
        return self.quantity_current < self.quantity_min

    def get_absolute_url(self):
        return reverse("part_details", kwargs={"pk": self.pk})


class PartStorageCollectionManager(models.Manager):

    def get_queryset(self):
        return super(PartStorageCollectionManager, self).get_queryset().select_related(
            'storage',
            'part',
            'storage__room',
            'storage__room__site',
        ).order_by('-quantity', 'part__part_number')


class PartStorageCollection(models.Model):

    part = models.ForeignKey(
        Part,
        verbose_name=_l("part"),
        on_delete=models.CASCADE,
        help_text=_l("Select the part to be associated with a Storage"),
    )
    storage = models.ForeignKey(
        Storage,
        verbose_name=_l("storage"),
        help_text=_l("Select the Storage to be associated with this Part"),
        on_delete=models.CASCADE,
    )

    quantity = models.IntegerField(
        verbose_name=_l("storage"),
        help_text=_l("Quantity of parts in this storage"),
    )

    objects = PartStorageCollectionManager()

    class Meta:
        unique_together = ('part', 'storage')
        default_permissions = ()

    def save(self, *args, **kwargs):
        self.quantity = self.quantity if self.quantity >= 0 else 0
        super(PartStorageCollection, self).save(*args, **kwargs)
        self.part.set_quantity_current()

    def __str__(self):
        locs = []
        if self.storage.room.site:
            locs.append(self.storage.room.site.name)
        locs.append(self.storage.room.name)
        if self.storage.location:
            locs.append(self.storage.location)
        locs.append('(%s)' % self.quantity)
        return ' - '.join(locs)


class PartSupplierCollection(models.Model):

    part = models.ForeignKey(
        Part,
        verbose_name=_l("part"),
        help_text=_l("Select the Part to be associated with this Supplier"),
        on_delete=models.CASCADE,
    )
    supplier = models.ForeignKey(
        Supplier,
        verbose_name=_l("supplier"),
        help_text=_l("Select the Supplier to be associated with this Part"),
        on_delete=models.CASCADE,
    )
    part_number = models.CharField(
        verbose_name=_l("part number"),
        max_length=32,
        null=True,
        blank=True,
        help_text=_l('Does this supplier have a different part number for this part'),
    )

    class Meta:
        unique_together = ('part', 'supplier', 'part_number')
        default_permissions = ()


class PartUsed(models.Model):

    service_event = models.ForeignKey(
        sl_models.ServiceEvent,
        verbose_name=_l("service event"),
        help_text=_l("Select the Service Event the part was used in"),
        on_delete=models.CASCADE,
    )
    part = models.ForeignKey(
        Part,
        verbose_name=_l("part"),
        help_text=_l('Select the part used'),
        on_delete=models.CASCADE,
    )
    from_storage = models.ForeignKey(
        Storage,
        verbose_name=_l("from storage"),
        help_text=_l('Select which Storage the parts were taken from'),
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
    )

    quantity = models.IntegerField(
        verbose_name=_l("quantity"),
        help_text=_l('Select how many parts were used from this Storage'),
    )

    def add_back_to_storage(self):

        if self.from_storage:
            try:
                psc = PartStorageCollection.objects.get(part=self.part, storage=self.from_storage)
                psc.quantity += self.quantity
                psc.save()
            except PartStorageCollection.DoesNotExist:
                PartStorageCollection.objects.create(part=self.part, storage=self.from_storage, quantity=self.quantity)

    def remove_from_storage(self):

        if self.from_storage:
            try:
                psc = PartStorageCollection.objects.get(part=self.part, storage=self.from_storage)
                psc.quantity -= self.quantity
                psc.save()
            except PartStorageCollection.DoesNotExist:
                pass
