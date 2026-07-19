import api from "@/lib/api";

export const paymentsApi = {
  config: () => api.get("/payments/config").then((r) => r.data),

  createOrder: (programId) =>
    api.post("/payments/order", { program_id: programId }).then((r) => r.data),

  markPaidDummy: (programId) =>
    api.post("/payments/mark-paid", { program_id: programId }).then((r) => r.data),

  verifyPayment: ({ order_id, payment_id, signature }) =>
    api
      .post("/payments/verify", {
        razorpay_order_id: order_id,
        razorpay_payment_id: payment_id,
        razorpay_signature: signature,
      })
      .then((r) => r.data),

  myPayments: (page = 1, page_size = 20) =>
    api
      .get("/payments/me", { params: { page, page_size } })
      .then((r) => r.data),

  downloadInvoiceUrl: (purchaseId) => {
    // used with a fetch + blob so we can attach Authorization header.
    return `/payments/invoice/${purchaseId}`;
  },

  downloadInvoiceBlob: (purchaseId) =>
    api
      .get(`/payments/invoice/${purchaseId}`, { responseType: "blob" })
      .then((r) => r.data),

  // ---- Subscription (Razorpay AutoPay / UPI Mandate) ---------------------
  subscriptionInit: (programId) =>
    api
      .post("/payments/subscription/init", { program_id: programId })
      .then((r) => r.data),

  subscriptionVerify: (subscriptionId) =>
    api
      .post(`/payments/subscription/${subscriptionId}/verify`)
      .then((r) => r.data),

  subscriptionCancel: (subscriptionId) =>
    api
      .post(`/payments/subscription/${subscriptionId}/cancel`)
      .then((r) => r.data),

  mySubscriptions: () =>
    api.get("/payments/subscription/me").then((r) => r.data),

  enrolFree: (programId) =>
    api.post(`/programs/${programId}/enrol-free`).then((r) => r.data),

  reconcileOrder: (razorpayOrderId) =>
    api
      .post("/payments/reconcile-order", { razorpay_order_id: razorpayOrderId })
      .then((r) => r.data),

  myEnrolments: () =>
    api.get("/programs/me/enrolments").then((r) => r.data),

  // ------ Admin ------
  adminList: (params) =>
    api.get("/payments/admin/transactions", { params }).then((r) => r.data),

  adminSummary: () =>
    api.get("/payments/admin/summary").then((r) => r.data),

  adminRefund: (purchaseId, reason) =>
    api
      .post(`/payments/admin/transactions/${purchaseId}/refund`, { reason })
      .then((r) => r.data),

  adminGetSettings: () =>
    api.get("/payments/admin/settings").then((r) => r.data),

  adminUpdateSettings: (payload) =>
    api.put("/payments/admin/settings", payload).then((r) => r.data),
};

/**
 * Load Razorpay Checkout.js on demand.
 * Returns a Promise resolving to `window.Razorpay` or null if it fails.
 */
export function loadRazorpayScript() {
  return new Promise((resolve) => {
    if (typeof window === "undefined") return resolve(null);
    if (window.Razorpay) return resolve(window.Razorpay);
    const s = document.createElement("script");
    s.src = "https://checkout.razorpay.com/v1/checkout.js";
    s.async = true;
    s.onload = () => resolve(window.Razorpay || null);
    s.onerror = () => resolve(null);
    document.body.appendChild(s);
  });
}
