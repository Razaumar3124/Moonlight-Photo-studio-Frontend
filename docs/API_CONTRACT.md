<!--
  OWNER: backend. This file is the source of truth for the API, received from the backend dev
  on 2026-11-05 and stored verbatim. Frontend mirror: frontend/src/types/api/.
  Frontend mismatches & open questions: docs/API_ALIGNMENT.md. Don't edit this file to "fix"
  a mismatch; raise it in API_ALIGNMENT.md and let the backend update the contract.
-->

# Moonlight Photo Studio – API Contract Documentation

## 1. Overview & General Conventions

- **Base URL**: `/api/v1`
- **Protocol**: HTTPS (REST over HTTP/1.1 or HTTP/2)
- **Data Format**: `application/json` (except photo upload endpoints which use `multipart/form-data`)
- **Character Encoding**: UTF-8
- **Date/Time Standard**: ISO-8601 UTC string (`YYYY-MM-DDTHH:MM:SS.sssZ`)
- **Geometry Internal Units**: Inches (`inches`), Top-Left origin `(x=0, y=0)`
- **Monetary Representation**: Fixed-precision numeric strings (`"1499.50"`) or 2-decimal floats (`1499.50`) with explicit ISO currency code (`"INR"`).

### Standard Error Response Envelope

All error responses strictly adhere to this standardized schema:

```json
{
  "error": {
    "code": "RESOURCE_NOT_FOUND",
    "message": "The requested layout design was not found.",
    "details": [
      {
        "field": "design_id",
        "issue": "No design exists with ID '67253a912e5c6a1b2c3d4e5f'"
      }
    ],
    "timestamp": "2026-11-01T22:45:00.000Z"
  }
}
```

### Standard HTTP Status Codes

| Code                       | Meaning                  | Usage                                                    |
| -------------------------- | ------------------------ | -------------------------------------------------------- |
| `200 OK`                   | Success                  | Successful GET, PUT, PATCH, or operational POST          |
| `201 Created`              | Created                  | Resource successfully created via POST                   |
| `204 No Content`           | No Content               | Successful deletion                                      |
| `400 Bad Request`          | Client Error             | Malformed payload or business logic constraint violation |
| `401 Unauthorized`         | Auth Required            | Missing, expired, or invalid JWT token                   |
| `403 Forbidden`            | Access Denied            | Authenticated user lacks permission for this resource    |
| `404 Not Found`            | Not Found                | Requested entity does not exist                          |
| `422 Unprocessable Entity` | Schema Validation Failed | Pydantic validation failure (type, range, missing field) |
| `500 Internal Error`       | Server Failure           | Unhandled server error                                   |

---

## 2. Authentication & User Management

### 2.1 Register User

- **Method**: `POST`
- **URL**: `/api/v1/auth/register`
- **Auth**: None

#### Request

```json
{
  "email": "customer@example.com",
  "password": "SecurePassword123!",
  "full_name": "Aarav Sharma",
  "phone": "+919876543210"
}
```

#### Response (`201 Created`)

```json
{
  "user": {
    "id": 1,
    "email": "customer@example.com",
    "full_name": "Aarav Sharma",
    "phone": "+919876543210",
    "role": "customer",
    "is_active": true,
    "created_at": "2026-11-01T22:45:00.000Z"
  },
  "tokens": {
    "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
    "refresh_token": "dGhpcy1pcy1hLXZhbGlkLXJlZnJlc2gtdG9rZW4...",
    "token_type": "bearer",
    "expires_in": 3600
  }
}
```

### 2.2 Login

- **Method**: `POST`
- **URL**: `/api/v1/auth/login`
- **Auth**: None

#### Request

```json
{
  "email": "customer@example.com",
  "password": "SecurePassword123!"
}
```

#### Response (`200 OK`)

```json
{
  "user": {
    "id": 1,
    "email": "customer@example.com",
    "full_name": "Aarav Sharma",
    "role": "customer",
    "is_active": true
  },
  "tokens": {
    "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
    "refresh_token": "dGhpcy1pcy1hLXZhbGlkLXJlZnJlc2gtdG9rZW4...",
    "token_type": "bearer",
    "expires_in": 3600
  }
}
```

### 2.3 Get Current User Profile

- **Method**: `GET`
- **URL**: `/api/v1/auth/me`
- **Auth**: Bearer Token

#### Response (`200 OK`)

```json
{
  "id": 1,
  "email": "customer@example.com",
  "full_name": "Aarav Sharma",
  "phone": "+919876543210",
  "role": "customer",
  "is_active": true,
  "created_at": "2026-11-01T22:45:00.000Z"
}
```

---

## 3. Frame Catalog & Materials

### 3.1 List Frame Materials

- **Method**: `GET`
- **URL**: `/api/v1/frame-materials`
- **Auth**: Optional / Public

#### Query Parameters

- `category` (optional, string: `"wood" | "metal" | "synthetic"`)
- `available_only` (optional, boolean, default: `true`)

#### Response (`200 OK`)

```json
{
  "items": [
    {
      "id": 1,
      "code": "teak-wood-natural",
      "name": "Natural Teak Wood",
      "category": "wood",
      "finish": "Satin Lacquer",
      "base_price_per_linear_inch": "14.50",
      "waste_factor_percentage": 10.0,
      "thumbnail_url": "/static/materials/teak-natural.webp",
      "is_available": true
    },
    {
      "id": 2,
      "code": "matte-black-aluminum",
      "name": "Matte Black Anodized Aluminum",
      "category": "metal",
      "finish": "Brushed Matte",
      "base_price_per_linear_inch": "18.00",
      "waste_factor_percentage": 5.0,
      "thumbnail_url": "/static/materials/matte-black-alu.webp",
      "is_available": true
    }
  ],
  "total": 2
}
```

### 3.2 List Frame Moldings

- **Method**: `GET`
- **URL**: `/api/v1/frames`
- **Auth**: Optional / Public

#### Query Parameters

- `material_id` (optional, integer)
- `color` (optional, string)
- `min_width` (optional, number in inches)
- `max_width` (optional, number in inches)

#### Response (`200 OK`)

```json
{
  "items": [
    {
      "id": 10,
      "sku": "FRM-TK-MOD-01",
      "name": "Modern Slender Teak",
      "material_id": 1,
      "material_name": "Natural Teak Wood",
      "profile_width_inches": 0.75,
      "profile_depth_inches": 1.25,
      "rabbet_depth_inches": 0.5,
      "price_per_linear_inch": "18.50",
      "available_colors": ["Natural Honey", "Dark Walnut", "Ebony Black"],
      "thumbnail_url": "/static/frames/slender-teak.webp",
      "is_active": true
    }
  ],
  "total": 1
}
```

---

## 4. Photo Management

### 4.1 Upload Photograph

- **Method**: `POST`
- **URL**: `/api/v1/photos/upload`
- **Auth**: Bearer Token
- **Content-Type**: `multipart/form-data`

#### Form Fields

- `file`: Binary file data (JPEG, PNG, WebP)

#### Response (`201 Created`)

```json
{
  "id": 101,
  "original_filename": "family_vacation_goa.jpg",
  "mime_type": "image/jpeg",
  "file_size_bytes": 4194304,
  "width_px": 4000,
  "height_px": 3000,
  "aspect_ratio": 1.3333,
  "suggested_orientation": "landscape",
  "thumbnail_url": "/api/v1/photos/101/thumbnail",
  "preview_url": "/api/v1/photos/101/preview",
  "created_at": "2026-11-01T22:45:00.000Z"
}
```

### 4.2 List User Photos

- **Method**: `GET`
- **URL**: `/api/v1/photos`
- **Auth**: Bearer Token

#### Response (`200 OK`)

```json
{
  "items": [
    {
      "id": 101,
      "original_filename": "family_vacation_goa.jpg",
      "width_px": 4000,
      "height_px": 3000,
      "aspect_ratio": 1.3333,
      "thumbnail_url": "/api/v1/photos/101/thumbnail",
      "created_at": "2026-11-01T22:45:00.000Z"
    }
  ],
  "total": 1
}
```

---

## 5. Layout Templates

### 5.1 List Templates

- **Method**: `GET`
- **URL**: `/api/v1/templates`
- **Auth**: Optional / Public

#### Query Parameters

- `category` (optional, `"grid" | "salon" | "triptych" | "staircase" | "focal_center"`)
- `min_frames` (optional, integer)
- `max_frames` (optional, integer)

#### Response (`200 OK`)

```json
{
  "items": [
    {
      "id": 1,
      "slug": "classic-grid-3x2",
      "name": "Classic 6-Frame Gallery Grid",
      "description": "Uniform 3 column by 2 row balanced gallery wall with 2-inch standard spacing.",
      "category": "grid",
      "min_wall_width_inches": 72.0,
      "min_wall_height_inches": 48.0,
      "recommended_wall_width_inches": 96.0,
      "recommended_wall_height_inches": 60.0,
      "slots_count": 6,
      "slots": [
        {
          "slot_id": "slot-1",
          "relative_x_ratio": 0.15,
          "relative_y_ratio": 0.2,
          "default_photo_width_inches": 12.0,
          "default_photo_height_inches": 16.0,
          "aspect_ratio": 0.75
        }
      ],
      "thumbnail_url": "/static/templates/classic-grid-3x2.svg"
    }
  ],
  "total": 1
}
```

---

## 6. Geometry Engine & Layout Validation

### 6.1 Validate Layout

Pure deterministic mathematical validation of frames on the wall.

- **Method**: `POST`
- **URL**: `/api/v1/geometry/validate-layout`
- **Auth**: None / Optional

#### Request

```json
{
  "wall": {
    "width_inches": 120.0,
    "height_inches": 96.0,
    "safe_margin_inches": 6.0
  },
  "frames": [
    {
      "item_id": "frame-item-1",
      "x_inches": 12.0,
      "y_inches": 18.0,
      "photo_width_inches": 16.0,
      "photo_height_inches": 20.0,
      "matting": {
        "top_inches": 2.0,
        "bottom_inches": 2.0,
        "left_inches": 2.0,
        "right_inches": 2.0
      },
      "frame_profile_width_inches": 1.0
    },
    {
      "item_id": "frame-item-2",
      "x_inches": 36.0,
      "y_inches": 18.0,
      "photo_width_inches": 16.0,
      "photo_height_inches": 20.0,
      "matting": {
        "top_inches": 2.0,
        "bottom_inches": 2.0,
        "left_inches": 2.0,
        "right_inches": 2.0
      },
      "frame_profile_width_inches": 1.0
    }
  ]
}
```

#### Response (`200 OK`)

```json
{
  "is_valid": true,
  "bounding_box": {
    "min_x": 12.0,
    "min_y": 18.0,
    "max_x": 58.0,
    "max_y": 44.0,
    "width_inches": 46.0,
    "height_inches": 26.0
  },
  "wall_coverage_percentage": 10.39,
  "errors": [],
  "warnings": [
    {
      "code": "LOW_WALL_COVERAGE",
      "message": "Arrangement occupies less than 20% of wall surface; consider larger mats or more frames."
    }
  ],
  "calculated_items": [
    {
      "item_id": "frame-item-1",
      "outer_x_inches": 12.0,
      "outer_y_inches": 18.0,
      "outer_width_inches": 22.0,
      "outer_height_inches": 26.0
    },
    {
      "item_id": "frame-item-2",
      "outer_x_inches": 36.0,
      "outer_y_inches": 18.0,
      "outer_width_inches": 22.0,
      "outer_height_inches": 26.0
    }
  ]
}
```

#### Collision Error Response Example (`422 Unprocessable Entity`)

```json
{
  "error": {
    "code": "GEOMETRY_COLLISION_DETECTED",
    "message": "Frames overlap or exceed wall boundaries.",
    "details": [
      {
        "field": "frames",
        "issue": "Frame 'frame-item-1' collides with frame 'frame-item-2'. Overlap delta: 2.00 inches horizontally."
      }
    ],
    "timestamp": "2026-11-01T22:45:00.000Z"
  }
}
```

### 6.2 Generate Layout Arrangement

- **Method**: `POST`
- **URL**: `/api/v1/geometry/generate-layout`
- **Auth**: None / Optional

#### Request

```json
{
  "wall": {
    "width_inches": 120.0,
    "height_inches": 96.0,
    "margin_inches": 8.0
  },
  "photo_ids": [101, 102, 103],
  "layout_style": "triptych",
  "spacing_inches": 3.0,
  "target_alignment": "center_eye_level",
  "eye_level_height_inches": 57.0
}
```

#### Response (`200 OK`)

```json
{
  "layout_type": "triptych",
  "bounding_box": {
    "min_x": 25.5,
    "min_y": 42.0,
    "max_x": 94.5,
    "max_y": 72.0,
    "width_inches": 69.0,
    "height_inches": 30.0
  },
  "items": [
    {
      "slot_index": 0,
      "photo_id": 101,
      "x_inches": 25.5,
      "y_inches": 42.0,
      "photo_width_inches": 16.0,
      "photo_height_inches": 24.0,
      "matting": {
        "top_inches": 2.0,
        "bottom_inches": 2.0,
        "left_inches": 2.0,
        "right_inches": 2.0
      },
      "frame_profile_width_inches": 0.75,
      "total_width_inches": 21.5,
      "total_height_inches": 29.5
    }
  ]
}
```

---

## 7. Pricing Engine

### 7.1 Calculate Price Breakdown

Pure deterministic financial computation using `Decimal`.

- **Method**: `POST`
- **URL**: `/api/v1/pricing/calculate`
- **Auth**: None / Optional

#### Request

```json
{
  "items": [
    {
      "item_id": "frame-item-1",
      "frame_id": 10,
      "photo_width_inches": 16.0,
      "photo_height_inches": 20.0,
      "matting": {
        "enabled": true,
        "top_inches": 2.0,
        "bottom_inches": 2.0,
        "left_inches": 2.0,
        "right_inches": 2.0,
        "matboard_type": "archival_white"
      },
      "glass_type": "museum_uv",
      "include_print": true
    }
  ],
  "pincode": "400001"
}
```

#### Response (`200 OK`)

```json
{
  "currency": "INR",
  "items_breakdown": [
    {
      "item_id": "frame-item-1",
      "dimensions": {
        "opening_width_inches": 16.0,
        "opening_height_inches": 20.0,
        "glass_mat_width_inches": 20.0,
        "glass_mat_height_inches": 24.0,
        "frame_outer_width_inches": 21.5,
        "frame_outer_height_inches": 25.5,
        "perimeter_linear_inches": 94.0,
        "area_square_inches": 480.0
      },
      "molding_cost": "1739.00",
      "matting_cost": "480.00",
      "glazing_cost": "720.00",
      "printing_cost": "350.00",
      "assembly_cost": "250.00",
      "item_subtotal": "3539.00"
    }
  ],
  "summary": {
    "total_molding": "3539.00",
    "subtotal": "3539.00",
    "discount_amount": "0.00",
    "tax_gst_amount": "637.02",
    "shipping_estimate": "350.00",
    "final_total": "4526.02"
  }
}
```

---

## 8. Designs & Versions Management

### 8.1 Create Design (Draft)

- **Method**: `POST`
- **URL**: `/api/v1/designs`
- **Auth**: Bearer Token

#### Request

```json
{
  "title": "Living Room Gallery Wall",
  "description": "Accent wall above 3-seater sofa",
  "wall": {
    "width_inches": 132.0,
    "height_inches": 108.0,
    "color_hex": "#F4F1EA",
    "texture": "plaster_smooth"
  }
}
```

#### Response (`201 Created`)

```json
{
  "id": 501,
  "user_id": 1,
  "title": "Living Room Gallery Wall",
  "description": "Accent wall above 3-seater sofa",
  "wall": {
    "width_inches": 132.0,
    "height_inches": 108.0,
    "color_hex": "#F4F1EA",
    "texture": "plaster_smooth"
  },
  "current_version_id": null,
  "status": "draft",
  "created_at": "2026-11-01T22:45:00.000Z",
  "updated_at": "2026-11-01T22:45:00.000Z"
}
```

### 8.2 Save Layout Version to Design

- **Method**: `POST`
- **URL**: `/api/v1/designs/{id}/versions`
- **Auth**: Bearer Token

#### Request

```json
{
  "layout_type": "custom",
  "template_id": null,
  "items": [
    {
      "item_id": "item-1",
      "frame_id": 10,
      "photo_id": 101,
      "position_x_inches": 30.0,
      "position_y_inches": 35.0,
      "photo_width_inches": 16.0,
      "photo_height_inches": 20.0,
      "matting": {
        "color_hex": "#FFFFFF",
        "top_inches": 2.0,
        "bottom_inches": 2.0,
        "left_inches": 2.0,
        "right_inches": 2.0
      },
      "glass_type": "museum_uv"
    }
  ]
}
```

#### Response (`201 Created`)

```json
{
  "version_id": 1001,
  "design_id": 501,
  "version_number": 1,
  "items_count": 1,
  "bounding_box": {
    "min_x": 30.0,
    "min_y": 35.0,
    "max_x": 51.5,
    "max_y": 60.5,
    "width_inches": 21.5,
    "height_inches": 25.5
  },
  "estimated_price": {
    "subtotal": "3539.00",
    "tax": "637.02",
    "total": "4176.02",
    "currency": "INR"
  },
  "created_at": "2026-11-01T22:45:00.000Z"
}
```

### 8.3 Get Design Details

- **Method**: `GET`
- **URL**: `/api/v1/designs/{id}`
- **Auth**: Bearer Token

#### Response (`200 OK`)

```json
{
  "id": 501,
  "title": "Living Room Gallery Wall",
  "status": "saved",
  "wall": {
    "width_inches": 132.0,
    "height_inches": 108.0,
    "color_hex": "#F4F1EA",
    "texture": "plaster_smooth"
  },
  "current_version": {
    "id": 1001,
    "version_number": 1,
    "layout_type": "custom",
    "items": [
      {
        "item_id": "item-1",
        "frame_id": 10,
        "photo_id": 101,
        "position_x_inches": 30.0,
        "position_y_inches": 35.0,
        "photo_width_inches": 16.0,
        "photo_height_inches": 20.0,
        "matting": {
          "color_hex": "#FFFFFF",
          "top_inches": 2.0,
          "bottom_inches": 2.0,
          "left_inches": 2.0,
          "right_inches": 2.0
        },
        "glass_type": "museum_uv",
        "total_width_inches": 21.5,
        "total_height_inches": 25.5,
        "calculated_price": "3539.00"
      }
    ],
    "bounding_box": {
      "min_x": 30.0,
      "min_y": 35.0,
      "max_x": 51.5,
      "max_y": 60.5,
      "width_inches": 21.5,
      "height_inches": 25.5
    }
  },
  "created_at": "2026-11-01T22:45:00.000Z",
  "updated_at": "2026-11-01T22:45:00.000Z"
}
```

---

## 9. Quotation Requests

### 9.1 Submit Quotation Request

- **Method**: `POST`
- **URL**: `/api/v1/quotes`
- **Auth**: Bearer Token

#### Request

```json
{
  "design_id": 501,
  "layout_version_id": 1001,
  "contact": {
    "full_name": "Aarav Sharma",
    "email": "customer@example.com",
    "phone": "+919876543210",
    "shipping_address": "Flat 402, Sea Green Apartments, Worli",
    "city": "Mumbai",
    "state": "Maharashtra",
    "postal_code": "400018"
  },
  "special_instructions": "Please include hanging hardware kit suitable for drywall."
}
```

#### Response (`201 Created`)

```json
{
  "id": 2001,
  "quote_number": "SQ-2026-11-0012",
  "status": "pending_review",
  "design_id": 501,
  "pricing_summary": {
    "subtotal": "3539.00",
    "tax_gst": "637.02",
    "estimated_shipping": "350.00",
    "total_estimated": "4526.02",
    "currency": "INR"
  },
  "expires_at": "2026-11-15T23:59:59.000Z",
  "created_at": "2026-11-01T22:45:00.000Z"
}
```

### 9.2 List User Quotes

- **Method**: `GET`
- **URL**: `/api/v1/quotes`
- **Auth**: Bearer Token

#### Response (`200 OK`)

```json
{
  "items": [
    {
      "id": 2001,
      "quote_number": "SQ-2026-11-0012",
      "design_id": 501,
      "design_title": "Living Room Gallery Wall",
      "total_amount": "4526.02",
      "currency": "INR",
      "status": "pending_review",
      "created_at": "2026-11-01T22:45:00.000Z"
    }
  ],
  "total": 1
}
```
